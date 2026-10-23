"""Gurobi runs with Gurobi's own cuts on or off and user cut generators attached.

With ``builtin_cuts=False`` every run sets ``Cuts=0``, ``Presolve=0`` and
``PreCrush=1``, checks that the settings took effect, and reads the
"Cutting planes" section of Gurobi's log, so any built-in cut that slipped
through shows up in ``RunResult.backend_cuts``.
"""

from __future__ import annotations

import os
import re
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import gurobipy as gp
from gurobipy import GRB

from branchcut.core.branching import BranchingRule
from branchcut.core.cuts import Cut, CutGenerator, SeparationContext
from branchcut.core.problem import MatrixProblem
from branchcut.core.tableau import SimplexTableau
from branchcut.core.types import Instance, RunResult

BUILTIN_CUTS_OFF = {"Cuts": 0, "Presolve": 0, "PreCrush": 1}
CUT_OPTION_DEFAULTS: dict[str, Any] = dict(
    root_rounds=10,             # manual LP rounds for root-placed generators
    max_cuts_per_round=50,      # cuts kept per generator call
    placement=None,             # override every generator's placement
    node_cuts_until=None,       # callback separates only while node count <= this (0: root node)
    max_tableau_size=2e7,       # skip the dense tableau above rows * columns
)
STATUS = {
    GRB.OPTIMAL: "optimal", GRB.INFEASIBLE: "infeasible", GRB.UNBOUNDED: "unbounded",
    GRB.INF_OR_UNBD: "inf_or_unbd", GRB.TIME_LIMIT: "time_limit",
    GRB.NODE_LIMIT: "node_limit", GRB.INTERRUPTED: "interrupted",
}


def problem_from_model(model: gp.Model) -> MatrixProblem:
    """Matrix view of a Gurobi model (uses ``getRow``; the matrix API needs scipy)."""
    model.update()
    xs, cons = model.getVars(), model.getConstrs()
    pos = {v.index: j for j, v in enumerate(xs)}
    rows = []
    for con in cons:
        row = model.getRow(con)
        idx = np.array([pos[row.getVar(k).index] for k in range(row.size())], int)
        val = np.array([row.getCoeff(k) for k in range(row.size())], float)
        rows.append((idx, val))
    return MatrixProblem(
        objective=np.array(model.getAttr("Obj", xs)),
        rows=tuple(rows),
        senses=tuple(model.getAttr("Sense", cons)),
        rhs=np.array(model.getAttr("RHS", cons)),
        lb=np.array(model.getAttr("LB", xs)),
        ub=np.array(model.getAttr("UB", xs)),
        is_integer=np.array([t in "BI" for t in model.getAttr("VType", xs)], bool),
        maximize=model.ModelSense == GRB.MAXIMIZE,
    )


def tableau_from_model(lp: gp.Model, is_integer: np.ndarray) -> SimplexTableau:
    """Tableau of a Gurobi LP solved to optimality with simplex."""
    p = problem_from_model(lp)
    xs, cons = lp.getVars(), lp.getConstrs()
    return SimplexTableau(
        p.dense_rows(), p.rhs, p.senses, p.lb, p.ub, np.array(lp.getAttr("X", xs)),
        np.array(lp.getAttr("VBasis", xs)), np.array(lp.getAttr("CBasis", cons)), is_integer,
    )


def parse_cut_section(log_text: str) -> dict[str, int]:
    """``{cut family: count}`` from the "Cutting planes:" block of a Gurobi log."""
    match = re.search(r"Cutting planes:\n((?:  .+\n)+)", log_text)
    if not match:
        return {}
    counts = {}
    for line in match.group(1).splitlines():
        name, count = line.strip().rsplit(":", 1)
        counts[name.strip()] = int(count)
    return counts


def _expr(cut: Cut, xs) -> gp.LinExpr:
    return gp.LinExpr(list(cut.coefficients.values()), [xs[j] for j in cut.coefficients])


def _attr(model: gp.Model, name: str):
    try:
        return getattr(model, name)
    except (gp.GurobiError, AttributeError):
        return None


@dataclass
class RunSpec:
    """One fully resolved solve."""

    instance: Instance
    generators: list[CutGenerator] = field(default_factory=list)
    builtin_cuts: bool = False
    branching: BranchingRule | None = None
    seed: int = 0
    time_limit: float | None = None
    solver_params: dict[str, Any] = field(default_factory=dict)
    cut_options: dict[str, Any] = field(default_factory=dict)
    record_cuts: bool = False
    record_solution: bool = False
    log_path: str | None = None


class _Separation:
    """Calls generators, enforces the return type, and keeps per-generator statistics."""

    def __init__(self, max_cuts: int, record: bool):
        self.max_cuts = max_cuts
        self.generated: Counter[str] = Counter()
        self.seconds: defaultdict[str, float] = defaultdict(float)
        self.log: list[dict[str, Any]] | None = [] if record else None

    def __call__(self, gen: CutGenerator, ctx: SeparationContext) -> list[Cut]:
        t = time.perf_counter()
        cuts = list(gen.separate(ctx) or [])[:self.max_cuts]
        self.seconds[gen.name] += time.perf_counter() - t
        for cut in cuts:
            if not isinstance(cut, Cut):
                raise TypeError(f"{gen.name}.separate must return Cut objects, got {type(cut).__name__}")
            if self.log is not None:
                self.log.append(dict(cut=cut, point=ctx.x, where=ctx.where, generator=gen.name))
        self.generated[gen.name] += len(cuts)
        return cuts


class GurobiSolver:
    name = "gurobi"

    def __init__(self, env: gp.Env | None = None):
        if env is None:
            env = gp.Env(empty=True)
            env.setParam("OutputFlag", 0)
            env.start()
        self.env = env

    @property
    def version(self) -> str:
        return ".".join(map(str, gp.gurobi.version()))

    def read(self, instance: Instance) -> gp.Model:
        return gp.read(instance.path, env=self.env)

    def load_problem(self, instance: Instance) -> MatrixProblem:
        model = self.read(instance)
        try:
            return problem_from_model(model)
        finally:
            model.dispose()

    def instance_stats(self, instance: Instance) -> dict[str, Any]:
        """Size, sense, and LP relaxation bound (no cuts, no presolve)."""
        model = self.read(instance)
        lp = model.relax()
        try:
            lp.Params.Presolve = 0
            lp.optimize()
            return dict(
                lp_bound=lp.ObjVal if lp.Status == GRB.OPTIMAL else None,
                maximize=model.ModelSense == GRB.MAXIMIZE,
                num_vars=model.NumVars, num_constrs=model.NumConstrs,
                num_int_vars=model.NumIntVars, num_bin_vars=model.NumBinVars,
            )
        finally:
            lp.dispose()
            model.dispose()

    def solve(self, spec: RunSpec) -> RunResult:
        unknown = set(spec.cut_options) - set(CUT_OPTION_DEFAULTS)
        if unknown:
            raise ValueError(f"unknown cut_options {sorted(unknown)}; known: {sorted(CUT_OPTION_DEFAULTS)}")
        opts = {**CUT_OPTION_DEFAULTS, **spec.cut_options}
        t0 = time.perf_counter()
        model = self.read(spec.instance)
        try:
            return self._solve(model, spec, opts, t0)
        finally:
            model.dispose()

    def _root_rounds(self, model, problem, gens, opts, sep, spec, t0):
        lp = model.relax()
        try:
            lp.Params.OutputFlag = 0
            lp.Params.Method = 1           # dual simplex: vertex solution with a basis
            lp.Params.Presolve = 0
            lp_vars = lp.getVars()
            needs_tableau = any(g.needs_tableau for g in gens)
            lp.optimize()
            if lp.Status != GRB.OPTIMAL:
                return [], [], 0
            history, added, skipped = [lp.ObjVal], [], 0
            for rnd in range(int(opts["root_rounds"])):
                if spec.time_limit is not None and time.perf_counter() - t0 > spec.time_limit:
                    break
                x = np.array(lp.getAttr("X", lp_vars))
                tab = None
                if needs_tableau:
                    if lp.NumConstrs * lp.NumVars <= opts["max_tableau_size"]:
                        tab = tableau_from_model(lp, problem.is_integer)
                    else:
                        skipped += 1
                ctx = SeparationContext(x, problem, "root", round=rnd, tableau=tab)
                new = [cut for gen in gens for cut in sep(gen, ctx)]
                if not new:
                    break
                for cut in new:
                    lp.addConstr(_expr(cut, lp_vars) <= cut.rhs)
                added += new
                lp.optimize()
                if lp.Status != GRB.OPTIMAL:   # invalid cuts can make the LP infeasible
                    break
                history.append(lp.ObjVal)
            return added, history, skipped
        finally:
            lp.dispose()

    def _solve(self, model: gp.Model, spec: RunSpec, opts: dict[str, Any], t0: float) -> RunResult:
        problem = problem_from_model(model)
        xs = model.getVars()
        root_gens, node_gens = [], []
        for gen in spec.generators:
            gen.prepare(problem, spec.seed)
            where = gen.resolved_placement(opts["placement"])
            if where in ("root", "both"):
                root_gens.append(gen)
            if where in ("node", "both"):
                node_gens.append(gen)
        sep = _Separation(int(opts["max_cuts_per_round"]), spec.record_cuts)

        root_cuts, history, skipped = [], [], 0
        if root_gens:
            root_cuts, history, skipped = self._root_rounds(model, problem, root_gens, opts, sep, spec, t0)
            for cut in root_cuts:
                model.addConstr(_expr(cut, xs) <= cut.rhs)

        params: dict[str, Any] = {}
        if not spec.builtin_cuts:
            params.update(BUILTIN_CUTS_OFF)
        elif node_gens:
            params["PreCrush"] = 1
        params["Seed"] = spec.seed
        if spec.branching is not None:
            params["VarBranch"] = spec.branching.var_branch
            prio = spec.branching.priorities(problem, spec.seed)
            if prio is not None:
                prio = [int(p) for p in prio]
                if len(prio) != len(xs):
                    raise ValueError(f"{spec.branching.name}: {len(prio)} priorities for {len(xs)} variables")
                model.setAttr("BranchPriority", xs, prio)
        if spec.time_limit is not None:
            params["TimeLimit"] = max(0.0, spec.time_limit - (time.perf_counter() - t0))
        params.update(spec.solver_params)

        logfile = spec.log_path or tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
        model.Params.LogToConsole = 0
        model.Params.OutputFlag = 1
        model.Params.LogFile = logfile
        for key, value in params.items():
            model.setParam(key, value)
        for key, value in params.items():          # enforce: the settings took effect
            if model.getParamInfo(key)[2] != value:
                raise RuntimeError(f"Gurobi parameter {key} did not take value {value!r}")

        errors: list[BaseException] = []
        root_lp: list[float] = []                  # root LP objective after the latest cut round
        node_limit = opts["node_cuts_until"]
        obj_con = model.ObjCon

        def callback(cb_model, where):
            if where != GRB.Callback.MIPNODE:
                return
            if cb_model.cbGet(GRB.Callback.MIPNODE_STATUS) != GRB.OPTIMAL:
                return
            count = int(cb_model.cbGet(GRB.Callback.MIPNODE_NODCNT))
            x = None
            if count == 0:
                x = np.array(cb_model.cbGetNodeRel(xs))
                root_lp[:] = [float(problem.objective @ x) + obj_con]
            if not node_gens or errors or (node_limit is not None and count > node_limit):
                return
            if x is None:
                x = np.array(cb_model.cbGetNodeRel(xs))
            ctx = SeparationContext(x, problem, "node", node_count=count)
            try:
                for gen in node_gens:
                    for cut in sep(gen, ctx):
                        cb_model.cbCut(_expr(cut, xs) <= cut.rhs)
            except Exception as exc:                 # re-raised after optimize()
                errors.append(exc)
                cb_model.terminate()

        model.optimize(callback)
        model.Params.LogFile = ""
        with open(logfile) as fh:
            log_text = fh.read()
        if spec.log_path is None:
            os.remove(logfile)
        if errors:
            raise errors[0]

        backend_cuts = parse_cut_section(log_text)
        user_applied = backend_cuts.pop("User", 0)
        has_sol = model.SolCount > 0
        best_bound = _attr(model, "ObjBound")
        return RunResult(
            status=STATUS.get(model.Status, "unknown"),
            objective=model.ObjVal if has_sol else None,
            best_bound=best_bound,
            gap=_attr(model, "MIPGap") if has_sol else None,
            root_bound=root_lp[0] if root_lp else best_bound,
            runtime=time.perf_counter() - t0,
            work=_attr(model, "Work"),
            nodes=int(model.NodeCount),
            simplex_iterations=float(model.IterCount),
            cuts_added=len(root_cuts) + user_applied,
            root_cuts_added=len(root_cuts),
            user_cuts_applied=user_applied,
            cuts_generated=dict(sep.generated),
            separation_seconds={k: round(v, 6) for k, v in sep.seconds.items()},
            backend_cuts=backend_cuts,
            root_bound_history=history,
            tableau_skipped=skipped,
            parameters=params,
            cut_log=sep.log,
            solution=np.array(model.getAttr("X", xs)) if spec.record_solution and has_sol else None,
        )
