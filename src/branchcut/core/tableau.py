"""Simplex tableau rebuilt from an optimal basis, for tableau-based cuts."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

BASIC, AT_LOWER, AT_UPPER, SUPERBASIC = 0, -1, -2, -3


class SimplexTableau:
    """Optimal simplex tableau written in "distance from bound" nonbasic variables.

    ``z = (x, s)`` stacks the structural variables and one slack per row, with
    ``A x + D s = rhs`` where ``D_ii = -1`` for ``>`` rows and ``+1`` otherwise.
    Row ``r`` reads ``z[basic[r]] + rows[r] @ y = value[r]`` with
    ``y_j = z_j - lb_j`` for a nonbasic variable at its lower bound and
    ``y_j = ub_j - z_j`` at its upper bound, so ``y = 0`` at the LP vertex.
    Columns of ``rows`` follow ``nonbasic``. Slacks are treated as continuous.

    Status codes follow Gurobi's ``VBasis``/``CBasis`` convention: ``0`` basic,
    ``-1`` at lower bound, ``-2`` at upper bound, ``-3`` superbasic. The
    construction is dense, so it suits instances with up to a few thousand rows.
    """

    def __init__(
        self,
        A: np.ndarray,
        rhs: np.ndarray,
        senses: Sequence[str],
        lb: np.ndarray,
        ub: np.ndarray,
        x: np.ndarray,
        var_status: np.ndarray,
        row_status: np.ndarray,
        is_integer: np.ndarray,
    ):
        self.m, self.n = m, n = A.shape
        self.A, self.rhs = A, rhs
        self.d = d = np.array([-1.0 if s == ">" else 1.0 for s in senses])
        status = np.concatenate([var_status, row_status])

        M = np.hstack([A, np.diag(d)])
        zval = np.concatenate([x, d * (rhs - A @ x)])
        z_int = np.concatenate([is_integer, np.zeros(m, bool)])
        self.z_lb = np.concatenate([lb, np.zeros(m)])
        self.z_ub = np.concatenate([ub, np.full(m, np.inf)])

        self.basic = np.flatnonzero(status == BASIC)
        self.nonbasic = np.flatnonzero(status != BASIC)
        if len(self.basic) != m:
            raise ValueError(f"basis has {len(self.basic)} basic variables for {m} rows")
        if np.any(status == SUPERBASIC):
            raise ValueError("superbasic variables present; solve the LP with simplex")

        self.at_upper = status[self.nonbasic] == AT_UPPER
        sign = np.where(self.at_upper, -1.0, 1.0)
        self.rows = sign * np.linalg.solve(M[:, self.basic], M[:, self.nonbasic])
        self.value = zval[self.basic]
        self.basic_integer = z_int[self.basic]
        self.nonbasic_integer = z_int[self.nonbasic]

    def fractional_rows(self, min_fractionality: float = 0.01) -> list[tuple[int, float]]:
        """``(row, f0)`` for fractional basic integer variables, most fractional first."""
        cand = []
        for r in range(self.m):
            f0 = self.value[r] - np.floor(self.value[r])
            if self.basic_integer[r] and min_fractionality < f0 < 1 - min_fractionality:
                cand.append((abs(f0 - 0.5), r, f0))
        return [(r, f0) for _, r, f0 in sorted(cand)]

    def to_x(self, g: np.ndarray, rhs: float = 1.0) -> tuple[np.ndarray, float]:
        """Map ``g @ y >= rhs`` to ``(alpha, beta)`` meaning ``alpha @ x >= beta``."""
        n = self.n
        alpha_z, beta = np.zeros(n + self.m), rhs
        for gj, j, up in zip(g, self.nonbasic, self.at_upper):
            if abs(gj) < 1e-12:
                continue
            if up:
                alpha_z[j] -= gj
                beta -= gj * self.z_ub[j]
            else:
                alpha_z[j] += gj
                beta += gj * self.z_lb[j]
        # substitute slacks: s = D (rhs - A x)
        alpha_x = alpha_z[:n] - (alpha_z[n:] * self.d) @ self.A
        beta -= (alpha_z[n:] * self.d) @ self.rhs
        alpha_x[np.abs(alpha_x) < 1e-11] = 0.0
        return alpha_x, beta
