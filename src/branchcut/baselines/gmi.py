"""Gomory mixed-integer cuts from the optimal simplex tableau."""

from __future__ import annotations

import numpy as np

from branchcut.core.cuts import Cut, CutGenerator, SeparationContext


def gmi_coefficients(a: np.ndarray, integer: np.ndarray, f0: float) -> np.ndarray:
    """GMI coefficients ``g`` (cut ``g @ y >= 1``) for tableau row ``z_k + a @ y = z_k*``.

    ``integer`` marks integer nonbasic columns and ``f0 = frac(z_k*)``.
    """
    fj = a - np.floor(a)
    g = np.zeros_like(a)
    lo, hi = integer & (fj <= f0), integer & (fj > f0)
    pos, neg = ~integer & (a > 0), ~integer & (a < 0)
    g[lo] = fj[lo] / f0
    g[hi] = (1 - fj[hi]) / (1 - f0)
    g[pos] = a[pos] / f0
    g[neg] = -a[neg] / (1 - f0)
    return g


class GomoryMixedIntegerCuts(CutGenerator):
    """One GMI cut per fractional basic integer variable, most fractional first.

    Unlike fractional Gomory cuts, GMI cuts stay valid when slacks or other
    variables are continuous.
    """

    name = "gmi"
    needs_tableau = True

    def __init__(self, min_fractionality: float = 0.01):
        self.min_fractionality = min_fractionality

    def separate(self, ctx: SeparationContext) -> list[Cut]:
        tab = ctx.tableau
        if tab is None:
            return []
        cuts = []
        for r, f0 in tab.fractional_rows(self.min_fractionality):
            alpha, beta = tab.to_x(gmi_coefficients(tab.rows[r], tab.nonbasic_integer, f0), 1.0)
            cuts.append(Cut.from_dense(alpha, beta, ">=", family=self.name))
        return cuts
