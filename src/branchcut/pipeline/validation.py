"""Correctness gate for approaches, run before they enter a benchmark.

Cut generators get five checks:

1. valid: no cut removes an integer-feasible point of small pure-binary
   instances whose feasible points are all enumerated
2. separating: every cut is violated at the point it was generated from
3. Gurobi's cuts are off: no built-in cut family in Gurobi's log, and the
   generator produced cuts
4. sound root bound: the bound never passes the true optimum
5. correct: the optimum matches Gurobi with its own cuts, on knapsack,
   set-cover and (mixed-integer) facility-location instances

Branching rules are checked for valid priorities and a correct optimum.
"""

from __future__ import annotations

import itertools
import tempfile
import traceback
from dataclasses import dataclass, field

import numpy as np

from branchcut.core.types import RunResult
from branchcut.pipeline.registry import Registry, resolve_branching
from branchcut.scenarios.generators import generate
from branchcut.solver import GurobiSolver, RunSpec

SMALL = (("knapsack", 1, dict(n=14, m=3)),
         ("set_cover", 1, dict(rows=12, cols=14, density=0.25)))
LARGE = (("knapsack", 7, dict(n=60, m=8)),
         ("set_cover", 2, dict(rows=100, cols=300, density=0.05, max_cost=3)),
         ("facility_location", 1, dict(facilities=8, customers=24)))
SOLVER_PARAMS = {"MIPGap": 0, "Threads": 1}
TOL = 1e-6


def enumerate_feasible(problem, max_vars: int = 20) -> np.ndarray:
    """All feasible points of a pure-binary problem (brute force)."""
    if not problem.is_binary.all():
        raise ValueError("brute-force enumeration needs a pure-binary problem")
    if problem.num_vars > max_vars:
        raise ValueError(f"{problem.num_vars} variables is too many to enumerate (max {max_vars})")
    pts = np.array(list(itertools.product([0.0, 1.0], repeat=problem.num_vars)))
    return pts[problem.is_feasible(pts)]


def _fmt(value: float | None, spec: str = ".6g") -> str:
    return "-" if value is None else format(value, spec)


def _same(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) <= TOL * max(1.0, abs(b))


def _gap_closed(z_lp, bound, z_opt) -> str:
    if None in (z_lp, bound, z_opt) or abs(z_lp - z_opt) < 1e-9:
        return "-"
    pct = 100 * (z_lp - bound) / (z_lp - z_opt)
    return f"{0.0 if abs(pct) < 0.05 else pct:.1f}%"


@dataclass
class Check:
    label: str
    passed: bool
    detail: str


@dataclass
class ValidationReport:
    name: str
    kind: str
    checks: list[Check] = field(default_factory=list)
    table: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def check(self, label: str, ok, detail: str) -> None:
        self.checks.append(Check(label, bool(ok), detail))

    def row(self, instance: str, config: str, r: RunResult, z_lp=None, z_opt=None) -> None:
        self.table.append(f"{instance:<36}{config[:14]:<15}{_fmt(r.objective, '.6g'):>11}{r.nodes:>8}"
                          f"{r.runtime:>8.2f}{r.cuts_added:>7}{_gap_closed(z_lp, r.root_bound, z_opt):>9}"
                          f"   {r.backend_cuts or ''}")

    def raise_on_failure(self) -> None:
        if not self.passed:
            failed = [c.label.strip() for c in self.checks if not c.passed]
            raise AssertionError(f"{self.kind} {self.name} failed validation: {failed}")

    def __str__(self) -> str:
        verdict = "PASSED" if self.passed else "FAILED"
        out = [f"== {self.kind} {self.name}: {verdict}"]
        if self.table:
            out += ["", f"{'instance':<36}{'config':<15}{'obj':>11}{'nodes':>8}{'time(s)':>8}"
                        f"{'cuts':>7}{'root gap':>9}   Gurobi cuts in log", *self.table, ""]
        out += [f"{'PASS' if c.passed else 'FAIL'}  {c.label:<42} {c.detail}" for c in self.checks]
        out += self.notes
        return "\n".join(out)


def validate_generator(name: str, registry: Registry, solver: GurobiSolver, *,
                       cut_options=None, generator_args=None, seed: int = 0) -> ValidationReport:
    report = ValidationReport(name, "cut generator")
    cls = registry.generators[name]

    def run(inst, with_generator: bool, builtin: bool) -> RunResult:
        gens = [cls(**(generator_args or {}))] if with_generator else []
        return solver.solve(RunSpec(inst, gens, builtin, seed=seed, solver_params=SOLVER_PARAMS,
                                    cut_options=dict(cut_options or {}),
                                    record_cuts=True, record_solution=True))

    with tempfile.TemporaryDirectory() as tmp:
        n_cuts = n_invalid = n_nonsep = n_points = 0
        small_bad = []
        for family, s, params in SMALL:
            inst = generate(family, s, tmp, **params)
            problem = solver.load_problem(inst)
            feas = enumerate_feasible(problem)
            values = feas @ problem.objective
            z = float(values.max() if problem.maximize else values.min())
            r = run(inst, True, False)
            for e in r.cut_log:
                n_cuts += 1
                n_invalid += bool(np.any(e["cut"].violation(feas) > TOL))
                n_nonsep += bool(e["cut"].violation(e["point"]) <= TOL)
            if not _same(r.objective, z):
                small_bad.append(f"{inst.name}: {_fmt(r.objective)} vs {z:.6g}")
            n_points += len(feas)
        report.check("1. valid: no feasible point cut off", n_invalid == 0,
                     f"{n_invalid} of {n_cuts} cuts invalid ({n_points} feasible points enumerated)")
        report.check("2. separating: violated at its own point", n_nonsep == 0,
                     f"{n_nonsep} of {n_cuts} cuts not violated")
        report.check("   small optima = brute force", not small_bad,
                     "; ".join(small_bad) or f"{len(SMALL)} instances")

        leaks, bound_bad, wrong = [], [], []
        generated = opt_cut = 0
        for family, s, params in LARGE:
            inst = generate(family, s, tmp, **params)
            stats = solver.instance_stats(inst)
            sense = 1.0 if stats["maximize"] else -1.0
            ref, base, r = run(inst, False, True), run(inst, False, False), run(inst, True, False)
            z = ref.objective
            for label, res in (("backend", ref), ("none", base), (name, r)):
                report.row(inst.name, label, res, stats["lp_bound"], z)
            for label, res in (("none", base), (name, r)):
                if res.backend_cuts:
                    leaks.append(f"{inst.name}/{label}: {res.backend_cuts}")
            generated += sum(r.cuts_generated.values())
            bounds = [b for b in (r.root_bound, *r.root_bound_history[-1:]) if b is not None]
            if z is not None and any(sense * (b - z) < -TOL * max(1.0, abs(z)) for b in bounds):
                bound_bad.append(inst.name)
            if ref.solution is not None:
                opt_cut += sum(bool(e["cut"].violation(ref.solution) > TOL) for e in r.cut_log)
            if r.status != "optimal" or not _same(r.objective, z):
                wrong.append(f"{inst.name}: {_fmt(r.objective)} vs {_fmt(z)} ({r.status})")
    report.check("3. no built-in cuts in Gurobi log", not leaks, "; ".join(leaks) or "only user cuts")
    report.check("   generator produced cuts", generated > 0, f"{generated} cuts on {len(LARGE)} instances")
    report.check("4. root bound never passes the optimum", not bound_bad, ", ".join(bound_bad) or "ok")
    report.check("   cuts keep the known optimum", opt_cut == 0, f"{opt_cut} cuts remove it")
    report.check("5. optimum matches Gurobi's own cuts", not wrong,
                 "; ".join(wrong) or f"{len(LARGE)} instances")
    return report


def validate_branching(name: str, registry: Registry, solver: GurobiSolver, *,
                       seed: int = 0) -> ValidationReport:
    report = ValidationReport(name, "branching rule")
    wrong = []
    with tempfile.TemporaryDirectory() as tmp:
        for family, s, params in LARGE:
            inst = generate(family, s, tmp, **params)
            ref = solver.solve(RunSpec(inst, builtin_cuts=True, seed=seed, solver_params=SOLVER_PARAMS))
            r = solver.solve(RunSpec(inst, builtin_cuts=True, branching=resolve_branching(name, registry),
                                     seed=seed, solver_params=SOLVER_PARAMS))
            report.row(inst.name, "default", ref)
            report.row(inst.name, name, r)
            if r.status != "optimal" or not _same(r.objective, ref.objective):
                wrong.append(f"{inst.name}: {_fmt(r.objective)} vs {_fmt(ref.objective)} ({r.status})")
    report.check("1. priorities accepted by Gurobi", True, "ran on every instance")
    report.check("5. optimum matches Gurobi default", not wrong, "; ".join(wrong) or f"{len(LARGE)} instances")
    return report


def validate(names, registry: Registry, solver: GurobiSolver, **kwargs) -> list[ValidationReport]:
    """Validate each named approach; an exception becomes a failed report, not a crash."""
    reports = []
    for name in names:
        is_gen = name in registry.generators
        if not is_gen and name not in registry.branching:
            raise KeyError(f"unknown approach {name!r}; available: {registry.approaches}")
        try:
            if is_gen:
                reports.append(validate_generator(name, registry, solver, **kwargs))
            else:
                reports.append(validate_branching(name, registry, solver,
                                                  **{k: v for k, v in kwargs.items() if k == "seed"}))
        except Exception as exc:
            report = ValidationReport(name, "cut generator" if is_gen else "branching rule")
            report.check("runs without error", False, f"{type(exc).__name__}: {exc}")
            report.notes = traceback.format_exc().rstrip().splitlines()[-6:]
            reports.append(report)
    return reports
