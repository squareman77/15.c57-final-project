"""Example approach: complemented MIR (c-MIR) cuts from single all-binary rows.

For a row ``a @ x <= b`` over binaries: complement every ``x_j* > 1/2``
(``x_j = 1 - x'_j``), divide by ``delta > 0``, and apply the MIR inequality

    sum_j (floor(a'_j/delta) + max(0, f_j - f) / (1 - f)) x'_j <= floor(b'/delta)

with ``f = frac(b'/delta)`` and ``f_j = frac(a'_j/delta)``. Each ``delta`` in
``{|a_j| : x_j* fractional}`` is tried and the most violated cut is kept.
"""

import numpy as np

from branchcut.api import Cut, CutGenerator, MatrixProblem, SeparationContext


class KnapsackCMIR(CutGenerator):
    """c-MIR cuts from single all-binary rows."""

    name = "cmir"

    def __init__(self, min_violation: float = 1e-4, min_frac: float = 0.05):
        self.min_violation = min_violation
        self.min_frac = min_frac

    def prepare(self, problem: MatrixProblem, seed: int) -> None:
        binary = problem.is_binary
        self.rows = [(idx, a, rhs) for idx, a, rhs in problem.less_equal_rows()
                     if len(idx) and binary[idx].all()]

    def separate(self, ctx: SeparationContext) -> list[Cut]:
        cuts = []
        for idx, a, rhs in self.rows:
            xr = ctx.x[idx]
            comp = xr > 0.5
            a_c = np.where(comp, -a, a)
            b_c = rhs - a[comp].sum()
            x_c = np.where(comp, 1 - xr, xr)
            frac = (xr > 1e-6) & (xr < 1 - 1e-6) & (a != 0)
            best = None
            for delta in np.unique(np.abs(a[frac])):
                beta = b_c / delta
                f = beta - np.floor(beta)
                if not self.min_frac < f < 1 - self.min_frac:
                    continue
                aj = a_c / delta
                g = np.floor(aj) + np.maximum(0.0, (aj - np.floor(aj)) - f) / (1 - f)
                viol = g @ x_c - np.floor(beta)
                if best is None or viol > best[0]:
                    best = (viol, g, np.floor(beta))
            if best is not None and best[0] > self.min_violation:
                _, g, r = best
                # undo complementing: g_j x'_j = g_j (1 - x_j) for complemented j
                coef = np.zeros(ctx.problem.num_vars)
                coef[idx] = np.where(comp, -g, g)
                cuts.append(Cut.from_dense(coef, r - g[comp].sum(), "<=", family=self.name))
        return cuts
