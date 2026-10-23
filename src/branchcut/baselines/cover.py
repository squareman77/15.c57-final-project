"""Extended cover inequalities for rows whose variables are all binary."""

from __future__ import annotations

import numpy as np

from branchcut.core.cuts import Cut, CutGenerator, SeparationContext
from branchcut.core.problem import MatrixProblem


def separate_cover(a: np.ndarray, rhs: float, x: np.ndarray, tol: float = 1e-6):
    """Greedy extended-cover separation for ``a @ x <= rhs``, ``a >= 0``, x binary.

    Returns ``(E, k)`` for the cut ``sum_{j in E} x_j <= k`` (local indices), or None.
    """
    order = np.argsort((1 - x) / np.maximum(a, 1e-12))
    C, weight = [], 0.0
    for j in order:
        if a[j] <= 0:
            continue
        C.append(j)
        weight += a[j]
        if weight > rhs + tol:
            break
    if weight <= rhs + tol:
        return None
    for j in sorted(C, key=lambda j: x[j]):        # make the cover minimal
        if weight - a[j] > rhs + tol:
            C.remove(j)
            weight -= a[j]
    if np.sum(1 - x[C]) >= 1 - tol:
        return None                                 # cover inequality not violated
    amax = a[C].max()
    E = sorted(set(C) | {j for j in range(len(a)) if a[j] >= amax})
    return E, len(C) - 1


class ExtendedCoverCuts(CutGenerator):
    """Extended cover cuts; negative coefficients are complemented (``x_j -> 1 - x_j``)."""

    name = "cover"

    def __init__(self, min_violation: float = 1e-4):
        self.min_violation = min_violation

    def prepare(self, problem: MatrixProblem, seed: int) -> None:
        binary = problem.is_binary
        self.rows = []
        for idx, a, rhs in problem.less_equal_rows():
            if len(idx) and binary[idx].all():
                neg = a < 0
                self.rows.append((idx, np.abs(a), rhs - a[neg].sum(), neg))

    def separate(self, ctx: SeparationContext) -> list[Cut]:
        cuts = []
        for idx, a, rhs, neg in self.rows:
            xc = np.where(neg, 1 - ctx.x[idx], ctx.x[idx])
            res = separate_cover(a, rhs, xc)
            if res is None:
                continue
            E, k = res
            if xc[E].sum() <= k + self.min_violation:
                continue
            # sum_{E} x'_j <= k  with  x'_j = 1 - x_j  for complemented j
            coef = {int(idx[j]): -1.0 if neg[j] else 1.0 for j in E}
            cuts.append(Cut(coef, float(k - neg[E].sum()), family=self.name))
        return cuts
