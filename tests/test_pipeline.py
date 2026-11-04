"""Discovery, validation gate, benchmark runner, resume and report."""

import json

import pytest

from branchcut.pipeline.benchmark import ValidationFailed, run_benchmark
from branchcut.pipeline.config import load_config
from branchcut.pipeline.registry import discover
from branchcut.pipeline.report import load_runs
from branchcut.pipeline.validation import validate

INVALID = '''
import numpy as np
from branchcut.api import Cut, CutGenerator

class ForbidMostFractional(CutGenerator):
    """Deliberately invalid: forbids the most fractional variable from being 1."""
    name = "forbid_most_fractional"

    def separate(self, ctx):
        j = int(np.argmin(np.abs(ctx.x - 0.5)))
        if not 0.01 < ctx.x[j] < 0.99:
            return []
        coef = np.zeros(len(ctx.x))
        coef[j] = 1.0
        return [Cut.from_dense(coef, 0.0)]
'''


@pytest.fixture()
def approach_dir(tmp_path):
    d = tmp_path / "approaches"
    d.mkdir()
    (d / "bad.py").write_text(INVALID)
    (d / "_ignored.py").write_text("raise RuntimeError('templates must not be loaded')\n")
    return d


def write_config(path, strategies, validate_=True, **extra):
    lines = [f'name = "{path.stem}"', f"strategies = {json.dumps(strategies)}",
             f"validate = {str(validate_).lower()}", "time_limit = 30", 'reference = "backend"',
             'baseline = "none"', *[f"{k} = {json.dumps(v)}" for k, v in extra.items()],
             "[solver]", "Threads = 1", "MIPGap = 0",
             "[[scenarios]]", 'family = "knapsack"', "count = 2", "seed = 100",
             "params = { n = 25, m = 4 }"]
    path.write_text("\n".join(lines) + "\n")
    return load_config(path)


def test_discovery_skips_templates_and_rejects_duplicates(approach_dir):
    reg = discover(approach_dir)
    assert "forbid_most_fractional" in reg.approaches
    (approach_dir / "dup.py").write_text(INVALID)
    with pytest.raises(ValueError, match="defined twice"):
        discover(approach_dir)


def test_validation_rejects_invalid_generator(approach_dir, solver):
    (report,) = validate(["forbid_most_fractional"], discover(approach_dir), solver)
    failed = {c.label.strip() for c in report.checks if not c.passed}
    assert not report.passed
    assert "1. valid: no feasible point cut off" in failed


def test_benchmark_runs_records_and_resumes(tmp_path, registry, solver):
    cfg = write_config(tmp_path / "mini.toml", ["backend", "none", "gmi", "cover+cmir"], seeds=[0, 1])
    run_dir = run_benchmark(cfg, registry, solver, results_dir=tmp_path / "results",
                            data_dir=tmp_path / "data", progress=lambda s: None)
    runs = load_runs(run_dir)
    assert len(runs) == 2 * 4 * 2
    assert {r["status"] for r in runs} == {"optimal"}
    objs = {(r["instance"], round(r["objective"], 6)) for r in runs}
    assert len(objs) == 2                                    # every strategy agrees per instance
    assert all(not r["backend_cuts"] for r in runs if r["strategy"] != "backend")
    env = json.loads((run_dir / "environment.json").read_text())
    assert env["approaches"]["cmir"]["sha256"]
    summary = (run_dir / "summary.md").read_text()
    assert "## Overview" in summary and "cover+cmir" in summary
    assert "## Problems\n\nnone" in summary
    assert (run_dir / "runs.csv").exists()

    run_benchmark(cfg, registry, solver, results_dir=tmp_path / "results", data_dir=tmp_path / "data",
                  resume=run_dir, progress=lambda s: None)
    assert len(load_runs(run_dir)) == len(runs)              # nothing re-run


def test_benchmark_gate_and_error_rows(tmp_path, approach_dir, solver):
    reg = discover(approach_dir)
    cfg = write_config(tmp_path / "gate.toml", ["backend", "none", "forbid_most_fractional"])
    with pytest.raises(ValidationFailed):
        run_benchmark(cfg, reg, solver, results_dir=tmp_path / "r", data_dir=tmp_path / "d",
                      progress=lambda s: None)

    (approach_dir / "crash.py").write_text(
        "from branchcut.api import CutGenerator\n"
        "class Crash(CutGenerator):\n    name = 'crash'\n"
        "    def separate(self, ctx):\n        raise RuntimeError('boom')\n")
    cfg = write_config(tmp_path / "errors.toml", ["backend", "none", "forbid_most_fractional", "crash"],
                       validate_=False)
    run_dir = run_benchmark(cfg, discover(approach_dir), solver, results_dir=tmp_path / "r",
                            data_dir=tmp_path / "d", progress=lambda s: None)
    runs = load_runs(run_dir)
    assert {r["status"] for r in runs if r["strategy"] == "crash"} == {"error"}
    summary = (run_dir / "summary.md").read_text()
    assert "RuntimeError: boom" in summary
    assert ": **wrong**" in summary                          # invalid cuts flagged at benchmark time
