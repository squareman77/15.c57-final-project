"""Starter cut generators."""

from __future__ import annotations

from collections.abc import Sequence

from branchcut.strategies.base import CutGenerator, LinearCut, NodeView


class NoCuts(CutGenerator):
    """Baseline strategy that adds no user-generated cuts."""

    name = "none"

    def separate(self, node: NodeView) -> Sequence[LinearCut]:
        return ()


class GomoryFractionalCuts(CutGenerator):
    """Extension point for Gomory fractional cuts; needs tableau access."""

    name = "gomory_fractional"
    required_capabilities = frozenset({"lp_tableau", "add_linear_constraints"})

    def separate(self, node: NodeView) -> Sequence[LinearCut]:
        raise NotImplementedError(
            "Gomory separation depends on the chosen backend's tableau representation"
        )
