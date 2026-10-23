"""Starter branching strategies."""

from __future__ import annotations

from collections.abc import Sequence

from branchcut.strategies.base import BranchDecision, BranchingRule, NodeView


class MostFractionalBranching(BranchingRule):
    """Choose the variable whose LP value is closest to one half.

    The caller supplies fractional variables in a stable order so ties are
    reproducible. Values are obtained from the node view's backend adapter in a
    future implementation; this baseline currently expects ``value_of``.
    """

    name = "most_fractional"

    def choose(self, node: NodeView, fractional_variables: Sequence[int]) -> BranchDecision:
        if not fractional_variables:
            raise ValueError("cannot branch when there are no fractional variables")
        value_of = getattr(node, "value_of", None)
        if value_of is None:
            raise NotImplementedError("NodeView must provide value_of(variable) to use this rule")
        variable = min(fractional_variables, key=lambda index: abs(value_of(index) - 0.5))
        return BranchDecision(variable=variable, value=value_of(variable), reason=self.name)
