"""Summaries of a results directory: ``summary.md`` (markdown tables) and ``runs.csv``."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from branchcut.pipeline.config import load_config

SHIFT = {"runtime": 1.0, "nodes": 10.0, "work": 1.0}
REL_TOL = 1e-6

DEFINITIONS = """\
* **sgm**: shifted geometric mean, with a shift of 1 s for time, 10 for nodes and 1 for Gurobi work units.
  Time is wall clock, including root cut rounds and Python separation; work is Gurobi's deterministic measure of solver effort only.
* **vs baseline**: ratio of sgm values over the instance × seed runs that both strategies completed, under the same branching rule. Below 1 means faster or smaller than the baseline.
* **time vs `<rule>`** (only with several branching rules): the same ratio, against the same cut strategy under the first branching rule in the config.
* **root gap closed**: (LP bound − root bound) / (LP bound − best known). The root bound is the root LP objective after the last round of cuts (Gurobi's, ours, or both), before branching; it measures cut strength alone, without root strong branching or integer rounding of the bound.
* **wrong**: the solver reported optimal but the objective differs from the reference, or a dual bound passed the proven optimum. A non-zero count means an invalid cut.
* **sep share**: share of the run's time spent inside cut generators.
"""


def load_runs(run_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "runs.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sgm(values, shift: float) -> float | None:
    """Shifted geometric mean, ignoring None."""
    v = np.array([x for x in values if x is not None], float)
    if not len(v):
        return None
    return float(np.exp(np.mean(np.log(v + shift))) - shift)


def gap_closed(lp_bound, root_bound, best_known) -> float | None:
    if None in (lp_bound, root_bound, best_known):
        return None
    if abs(lp_bound - best_known) <= 1e-9 * max(1.0, abs(best_known)):
        return None
    return (lp_bound - root_bound) / (lp_bound - best_known)


def _close(a, b) -> bool:
    return a is not None and b is not None and abs(a - b) <= REL_TOL * max(1.0, abs(b))


def _passes(bound, z, maximize) -> bool:
    """True when a dual bound is on the wrong side of the proven optimum ``z``."""
    if bound is None or z is None:
        return False
    tol = REL_TOL * max(1.0, abs(z))
    return bound < z - tol if maximize else bound > z + tol


def annotate(runs: list[dict[str, Any]], reference: str | None) -> dict[str, dict[str, Any]]:
    """Add ``best_known``, ``wrong`` and ``gap_closed`` to every run; return per-instance info."""
    by_instance: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in runs:
        by_instance[r["instance"]].append(r)
    info = {}
    for name, rs in by_instance.items():
        maximize = bool(rs[0].get("maximize"))
        optimal = [r["objective"] for r in rs if r["status"] == "optimal" and r["objective"] is not None]
        ref = [r["objective"] for r in rs if r["strategy"] == reference and r["status"] == "optimal"]
        if ref:
            z, proven = ref[0], True
        elif optimal:
            z, proven = Counter(round(v, 6) for v in optimal).most_common(1)[0][0], True
        else:
            primal = [r["objective"] for r in rs if r["objective"] is not None]
            z, proven = ((max(primal) if maximize else min(primal)) if primal else None), False
        for r in rs:
            r["best_known"] = z
            r["wrong"] = proven and (
                (r["status"] == "optimal" and not _close(r["objective"], z))
                or _passes(r.get("best_bound"), z, maximize) or _passes(r.get("root_bound"), z, maximize))
            r["gap_closed"] = gap_closed(r.get("lp_bound"), r.get("root_bound"), z)
        info[name] = dict(best_known=z, proven=proven, family=rs[0]["family"], maximize=maximize)
    return info


def _md(header: list[str], rows: list[list[Any]]) -> str:
    def cell(v):
        if v is None:
            return "–"
        if isinstance(v, float):
            if abs(v) < 1e-6:                     # floating-point noise
                return "0"
            return f"{v:.3g}" if abs(v) < 1000 else f"{v:,.0f}"
        return str(v)
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _mean(values) -> float | None:
    v = [x for x in values if x is not None]
    return float(np.mean(v)) if v else None


def _pct(value) -> float | None:
    return None if value is None else 100 * value


def summarize(run_dir: str | Path, *, write: bool = True) -> str:
    """Build the markdown summary of ``run_dir``; also writes ``summary.md`` and ``runs.csv``."""
    run_dir = Path(run_dir)
    runs = load_runs(run_dir)
    cfg_path = run_dir / "config.toml"
    cfg = load_config(cfg_path) if cfg_path.exists() else None       # same defaults as the benchmark
    title = cfg.name if cfg else run_dir.name
    env_path = run_dir / "environment.json"
    env = json.loads(env_path.read_text(encoding="utf-8")) if env_path.exists() else {}
    baseline = cfg.baseline if cfg else None
    reference = cfg.reference if cfg else None
    if not runs:
        return f"# {title}\n\nno runs recorded in {run_dir}\n"
    info = annotate(runs, reference)

    order = {s: i for i, s in enumerate(cfg.strategies if cfg else [])}
    branchings = sorted({r["branching"] for r in runs})
    label = (lambda s, b: s) if len(branchings) == 1 else (lambda s, b: f"{s} / {b}")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in runs:
        groups[(r["strategy"], r["branching"])].append(r)
    keys = sorted(groups, key=lambda k: (order.get(k[0], len(order)), k[0], k[1]))
    base = {(r["instance"], r["seed"], r["branching"]): r for r in runs
            if r["strategy"] == baseline and r["status"] != "error"}
    first_branching = (cfg.branching if cfg else branchings)[0]
    base_branching = {(r["instance"], r["seed"], r["strategy"]): r for r in runs
                      if r["branching"] == first_branching and r["status"] != "error"}

    def ratio(rs, metric, against=None):
        if against is None:
            pairs = [(r, base.get((r["instance"], r["seed"], r["branching"]))) for r in rs]
        else:
            pairs = [(r, against.get((r["instance"], r["seed"], r["strategy"]))) for r in rs]
        pairs = [(r, q) for r, q in pairs if q is not None]
        if not pairs:
            return None
        a = sgm([r[metric] for r, _ in pairs], SHIFT[metric])
        b = sgm([q[metric] for _, q in pairs], SHIFT[metric])
        return None if a is None or not b else a / b

    overview = []
    for key in keys:
        rs = groups[key]
        ok = [r for r in rs if r["status"] != "error"]
        statuses = Counter(r["status"] for r in rs)
        share = [sum(r["separation_seconds"].values()) / r["runtime"] for r in ok if r["runtime"] > 0]
        overview.append([
            label(*key), len(rs), statuses["optimal"], statuses["time_limit"], statuses["error"],
            sum(r["wrong"] for r in rs),
            sgm([r["runtime"] for r in ok], SHIFT["runtime"]), ratio(ok, "runtime"),
            sgm([r["nodes"] for r in ok], SHIFT["nodes"]), ratio(ok, "nodes"),
            sgm([r["work"] for r in ok], SHIFT["work"]),
            _pct(_mean(r["gap_closed"] for r in ok)), _mean(r["cuts_added"] for r in ok),
            _pct(_mean(share)),
        ] + ([ratio(ok, "runtime", base_branching)] if len(branchings) > 1 else []))

    families = sorted({r["family"] for r in runs})
    by_family_time, by_family_gap = [], []
    for key in keys:
        rs = [r for r in groups[key] if r["status"] != "error"]
        by_family_time.append([label(*key)] + [
            sgm([r["runtime"] for r in rs if r["family"] == f], SHIFT["runtime"]) for f in families])
        by_family_gap.append([label(*key)] + [
            _pct(_mean(r["gap_closed"] for r in rs if r["family"] == f)) for f in families])

    per_instance = []
    for name in sorted(info, key=lambda n: (info[n]["family"], n)):
        row: list[Any] = [name, info[name]["best_known"]]
        for key in keys:
            rs = [r for r in groups[key] if r["instance"] == name]
            if not rs:
                row.append(None)
                continue
            flags = [f for f, hit in (("ERR", any(r["status"] == "error" for r in rs)),
                                      ("WRONG", any(r["wrong"] for r in rs)),
                                      ("TL", any(r["status"] == "time_limit" for r in rs))) if hit]
            t = sgm([r["runtime"] for r in rs if r["status"] != "error"], SHIFT["runtime"])
            row.append(" ".join([f"{t:.2f}" if t is not None else "–", *flags]))
        per_instance.append(row)

    problems = [f"* `{r['instance']}` / `{r['strategy']}` / `{r['branching']}` / seed {r['seed']}: "
                + ("**wrong**" if r["wrong"] else r["message"].splitlines()[0])
                for r in runs if r["wrong"] or r["status"] == "error"]

    header = [f"# {title}", ""]
    if cfg and cfg.description:
        header += [cfg.description, ""]
    header += [f"* results: `{run_dir}`",
               f"* runs: {len(runs)} on {len(info)} instances, seeds {sorted({r['seed'] for r in runs})}, "
               f"time limit {cfg.time_limit if cfg and cfg.time_limit else '–'} s",
               f"* baseline: `{baseline or 'none set'}`, reference: "
               + (f"`{reference}`" if reference else "consensus of optimal runs"),
               f"* solver: {env.get('solver', 'gurobi')} {env.get('solver_version', '')}, "
               f"commit {str(env.get('git_commit'))[:10]}{' (dirty)' if env.get('git_dirty') else ''}", ""]
    text = "\n".join(header + [
        "## Overview", "",
        _md(["strategy", "runs", "optimal", "time limit", "errors", "wrong", "sgm time (s)",
             "time vs baseline", "sgm nodes", "nodes vs baseline", "sgm work", "root gap closed (%)",
             "cuts added", "sep share (%)"]
            + ([f"time vs {first_branching}"] if len(branchings) > 1 else []), overview), "",
        "## By family: sgm time (s)", "", _md(["strategy", *families], by_family_time), "",
        "## By family: mean root gap closed (%)", "", _md(["strategy", *families], by_family_gap), "",
        "## Per instance: sgm time (s) over seeds", "",
        "Flags: TL = time limit hit, ERR = error, WRONG = disagrees with the proven optimum.", "",
        _md(["instance", "best known", *[label(*k) for k in keys]], per_instance), "",
        "## Problems", "", "\n".join(problems) or "none", "",
        "## Definitions", "", DEFINITIONS,
    ])
    if write:
        (run_dir / "summary.md").write_text(text, encoding="utf-8")
        fields = list(dict.fromkeys(k for r in runs for k in r))
        with (run_dir / "runs.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for r in runs:
                writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()})
    return text
