"""Gurobi runs: built-in cuts off, user cuts in, errors surfaced, branching applied."""

import numpy as np
import pytest

from branchcut.baselines import ExtendedCoverCuts, GomoryMixedIntegerCuts
from branchcut.core.branching import BranchingRule
from branchcut.core.cuts import CutGenerator
from branchcut.scenarios.generators import generate
from branchcut.solver import RunSpec


class Crashes(CutGenerator):
    name = "crashes"

    def separate(self, ctx):
        raise ValueError("bug in generator")


class ReturnsTuples(CutGenerator):
    name = "returns_tuples"

    def separate(self, ctx):
        return [({0: 1.0}, 0.0)]


class ReversePriority(BranchingRule):
    name = "reverse"
    var_branch = 2

    def priorities(self, problem, seed):
        return np.arange(problem.num_vars)[::-1]


@pytest.fixture(scope="module")
def knapsack(tmp_path_factory):
    return generate("knapsack", 100, tmp_path_factory.mktemp("inst"), n=40, m=5)


def test_builtin_cuts_only_when_enabled(solver, knapsack):
    on = solver.solve(RunSpec(knapsack, builtin_cuts=True))
    off = solver.solve(RunSpec(knapsack, builtin_cuts=False))
    assert on.backend_cuts and not off.backend_cuts
    assert off.parameters["Cuts"] == 0 and off.parameters["Presolve"] == 0
    assert on.objective == off.objective


def test_user_cuts_counted(solver, knapsack):
    r = solver.solve(RunSpec(knapsack, [GomoryMixedIntegerCuts(), ExtendedCoverCuts()]))
    assert r.status == "optimal" and not r.backend_cuts
    assert r.root_cuts_added == r.cuts_generated["gmi"] > 0
    assert r.cuts_generated["cover"] > 0 and r.cuts_added >= r.root_cuts_added
    assert r.root_bound_history == sorted(r.root_bound_history, reverse=True)   # max problem


def test_root_bound_is_between_optimum_and_lp(solver, knapsack):
    stats = solver.instance_stats(knapsack)
    r = solver.solve(RunSpec(knapsack, [GomoryMixedIntegerCuts()]))
    assert stats["lp_bound"] + 1e-6 >= r.root_bound >= r.objective - 1e-6


@pytest.mark.parametrize("generator, error", [(Crashes(), ValueError), (ReturnsTuples(), TypeError)])
def test_generator_errors_surface(solver, knapsack, generator, error):
    with pytest.raises(error):
        solver.solve(RunSpec(knapsack, [generator]))


def test_tableau_generator_cannot_run_at_nodes(solver, knapsack):
    with pytest.raises(ValueError, match="root rounds"):
        solver.solve(RunSpec(knapsack, [GomoryMixedIntegerCuts()], cut_options={"placement": "node"}))


def test_unknown_cut_option_rejected(solver, knapsack):
    with pytest.raises(ValueError, match="unknown cut_options"):
        solver.solve(RunSpec(knapsack, cut_options={"rounds": 3}))


def test_branching_rule_applied(solver, knapsack):
    r = solver.solve(RunSpec(knapsack, builtin_cuts=True, branching=ReversePriority()))
    assert r.status == "optimal" and r.parameters["VarBranch"] == 2


def test_time_limit_respected(solver, tmp_path):
    inst = generate("knapsack", 3, tmp_path, n=150, m=15)
    r = solver.solve(RunSpec(inst, time_limit=0.5))
    assert r.status in ("time_limit", "optimal") and r.runtime < 5
