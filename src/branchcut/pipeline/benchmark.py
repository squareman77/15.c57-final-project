"""Run an experiment matrix: validate approaches, solve, and write one JSONL row per run.

Results go to ``results/<config name>/<timestamp>/``:

* ``config.toml``: copy of the config that produced them
* ``environment.json``: solver and Python versions, git commit, approach file hashes
* ``runs.jsonl``: one row per (instance, strategy, branching, seed), flushed as it runs
* ``summary.md`` and ``runs.csv``: written by ``report.summarize``
* ``logs/``: Gurobi logs, when ``keep_logs = true``

An interrupted benchmark continues with ``resume=<run dir>``; finished runs are skipped.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import branchcut
from branchcut.core.types import Instance, RunResult
from branchcut.pipeline.config import ExperimentConfig
from branchcut.pipeline.registry import Registry, Strategy, resolve_branching, resolve_strategy
from branchcut.pipeline.report import load_runs, summarize
from branchcut.pipeline.validation import validate
from branchcut.scenarios import build_instances
from branchcut.solver import GurobiSolver, RunSpec


class ValidationFailed(RuntimeError):
    def __init__(self, reports):
        self.reports = reports
        failed = [r.name for r in reports if not r.passed]
        super().__init__(f"approach validation failed: {', '.join(failed)}")


def run_key(row: dict[str, Any]) -> tuple:
    return row["instance"], row["strategy"], row["branching"], row["seed"]


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, check=True, timeout=10)
        return out.stdout.strip()
    except Exception:
        return None


def environment(config: ExperimentConfig, registry: Registry, solver: GurobiSolver,
                strategies: dict[str, Strategy]) -> dict[str, Any]:
    used = sorted({g for s in strategies.values() for g in s.generators} | set(config.branching))
    return dict(
        created=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        branchcut=branchcut.__version__,
        solver=solver.name,
        solver_version=solver.version,
        python=sys.version.split()[0],
        platform=platform.platform(),
        git_commit=_git("rev-parse", "HEAD"),
        git_dirty=bool(_git("status", "--porcelain")),
        approaches={n: dict(origin=registry.origins[n], sha256=registry.fingerprint(n)) for n in used},
    )


def plan(config: ExperimentConfig, registry: Registry, data_dir: str | Path = "data",
         only=None) -> tuple[list[Instance], dict[str, Strategy]]:
    """Resolve instances and strategies without solving anything."""
    config.check(registry)
    strategies = {label: resolve_strategy(label, registry, config.variants) for label in config.strategies}
    if only:
        missing = set(only) - set(strategies)
        if missing:
            raise ValueError(f"--only names {sorted(missing)} are not strategies of {config.name}")
        strategies = {k: v for k, v in strategies.items() if k in only}
    return build_instances(config.scenarios, data_dir), strategies


def _run_one(config: ExperimentConfig, registry: Registry, solver: GurobiSolver, inst: Instance,
             stats: dict[str, Any], strategy: Strategy, branching: str, seed: int,
             run_dir: Path) -> dict[str, Any]:
    log_path = None
    if config.keep_logs:
        log_path = str(run_dir / "logs" / f"{inst.name}__{strategy.label}__{branching}__s{seed}.log")
    t0 = time.perf_counter()
    try:
        result = solver.solve(RunSpec(
            instance=inst, generators=strategy.build(registry), builtin_cuts=strategy.builtin_cuts,
            branching=resolve_branching(branching, registry), seed=seed, time_limit=config.time_limit,
            solver_params={**config.solver, **strategy.solver_params},
            cut_options={**config.cut_options, **strategy.cut_options}, log_path=log_path,
        ))
    except Exception as exc:
        result = RunResult(status="error", runtime=time.perf_counter() - t0,
                           message=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=-4)}")
    return dict(instance=inst.name, family=inst.family, source=inst.source, strategy=strategy.label,
                cuts=strategy.cuts, branching=branching, seed=seed, time_limit=config.time_limit,
                **stats, **result.to_record())


def _progress_line(count: int, total: int, row: dict[str, Any]) -> str:
    obj = "-" if row["objective"] is None else f"{row['objective']:.6g}"
    return (f"[{count}/{total}] {row['instance']:<34} {row['strategy']:<16} {row['branching']:<12} "
            f"s{row['seed']}  {row['status']:<10} obj={obj:<12} nodes={row['nodes']:<7} "
            f"t={row['runtime']:.2f}s")


def run_benchmark(config: ExperimentConfig, registry: Registry, solver: GurobiSolver, *,
                  results_dir: str | Path = "results", data_dir: str | Path = "data",
                  resume: str | Path | None = None, only=None, skip_validation: bool = False,
                  progress: Callable[[str], None] = print) -> Path:
    """Run every (instance, seed, branching, strategy) and return the results directory."""
    instances, strategies = plan(config, registry, data_dir, only)

    if config.validate and not skip_validation:
        names = sorted({g for s in strategies.values() for g in s.generators if registry.is_approach(g)}
                       | {b for b in config.branching if registry.is_approach(b)})
        if names:
            progress(f"validating approaches: {', '.join(names)}")
            reports = validate(names, registry, solver, cut_options=config.cut_options)
            for report in reports:
                progress(f"{report}\n")
            if not all(r.passed for r in reports):
                raise ValidationFailed(reports)

    run_dir = Path(resume) if resume else Path(results_dir) / config.name / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    if config.path and not (run_dir / "config.toml").exists():
        shutil.copyfile(config.path, run_dir / "config.toml")
    if not (run_dir / "environment.json").exists():
        env = environment(config, registry, solver, strategies)
        (run_dir / "environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    if config.keep_logs:
        (run_dir / "logs").mkdir(exist_ok=True)

    done = {run_key(r) for r in load_runs(run_dir)}
    total = len(instances) * len(config.seeds) * len(config.branching) * len(strategies)
    progress(f"{config.name}: {len(instances)} instances x {len(strategies)} strategies x "
             f"{len(config.branching)} branching x {len(config.seeds)} seeds = {total} runs"
             + (f" ({len(done)} already done)" if done else "") + f" -> {run_dir}")
    count = 0
    with (run_dir / "runs.jsonl").open("a", encoding="utf-8") as fh:
        for inst in instances:
            stats = None
            for seed in config.seeds:
                for branching in config.branching:
                    for label, strategy in strategies.items():
                        count += 1
                        if (inst.name, label, branching, seed) in done:
                            continue
                        if stats is None:
                            stats = solver.instance_stats(inst)
                        row = _run_one(config, registry, solver, inst, stats, strategy, branching, seed, run_dir)
                        fh.write(json.dumps(row, default=float) + "\n")
                        fh.flush()
                        progress(_progress_line(count, total, row))
    summarize(run_dir)
    return run_dir
