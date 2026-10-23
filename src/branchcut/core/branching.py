"""Branching-rule interface.

Gurobi has no branching callback, so a rule cannot pick the branching variable
node by node. A rule is static instead: a Gurobi ``VarBranch`` strategy plus
optional per-variable ``BranchPriority`` values computed from the model.
"""

from __future__ import annotations

from collections.abc import Sequence

from branchcut.core.problem import MatrixProblem

# Gurobi VarBranch values
BUILTIN_BRANCHING = {
    "default": -1,
    "pseudo_reduced_cost": 0,
    "pseudo_shadow_price": 1,
    "max_infeasibility": 2,
    "most_fractional": 2,          # alias: Gurobi's maximum-infeasibility branching
    "strong": 3,
}


class BranchingRule:
    """Base class for branching rules; set ``name`` and override ``priorities``."""

    name: str = ""
    var_branch: int = -1

    def priorities(self, problem: MatrixProblem, seed: int) -> Sequence[int] | None:
        """Per-variable branching priority (higher is branched on first), or None."""
        return None


class GurobiBranching(BranchingRule):
    """One of Gurobi's built-in variable selection strategies."""

    def __init__(self, name: str, var_branch: int):
        self.name = name
        self.var_branch = var_branch
