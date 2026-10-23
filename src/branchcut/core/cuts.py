"""Cut-generator interface implemented by approach files."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from branchcut.core.problem import MatrixProblem
from branchcut.core.tableau import SimplexTableau

PLACEMENTS = ("auto", "root", "node", "both")


@dataclass(frozen=True)
class Cut:
    """Linear inequality ``sum_j coefficients[j] * x[j] <= rhs``.

    Cuts are added globally, so a cut must be valid for every integer-feasible
    point of the original model, not just for the current node.
    """

    coefficients: Mapping[int, float]
    rhs: float
    family: str = "user"

    @classmethod
    def from_dense(cls, coef, rhs: float, sense: str = "<=", family: str = "user") -> Cut:
        """Build from a dense ``coef @ x  sense  rhs`` with ``sense`` ``"<="`` or ``">="``."""
        if sense not in ("<=", ">="):
            raise ValueError(f"sense must be '<=' or '>=', got {sense!r}")
        sign = 1.0 if sense == "<=" else -1.0
        coef = np.asarray(coef, float)
        nz = np.flatnonzero(coef)
        return cls({int(j): sign * float(coef[j]) for j in nz}, sign * float(rhs), family)

    def violation(self, points) -> np.ndarray:
        """``lhs - rhs`` at one point ``(n,)`` or a stack ``(k, n)``; > 0 means violated."""
        points = np.asarray(points, float)
        idx = np.fromiter(self.coefficients.keys(), int, len(self.coefficients))
        val = np.fromiter(self.coefficients.values(), float, len(self.coefficients))
        return points[..., idx] @ val - self.rhs


@dataclass
class SeparationContext:
    """What a generator sees each time it is asked for cuts.

    ``x`` is the relaxation point to cut off. ``problem`` holds the original
    model rows, so cuts derived from them are globally valid. ``tableau`` is the
    optimal simplex tableau of the current root LP, present only in root rounds
    and only for generators with ``needs_tableau``.
    """

    x: np.ndarray
    problem: MatrixProblem
    where: str                     # "root" (manual LP rounds) or "node" (B&B callback)
    round: int = 0                 # root round number
    node_count: int = 0            # B&B nodes explored so far (callback only)
    tableau: SimplexTableau | None = None

    @property
    def relaxation_objective(self) -> float:
        return float(self.problem.objective @ self.x)

    def fractional(self, tol: float = 1e-6) -> np.ndarray:
        """Indices of integer variables whose value is fractional."""
        f = self.x - np.floor(self.x)
        return np.flatnonzero(self.problem.is_integer & (f > tol) & (f < 1 - tol))


class CutGenerator(ABC):
    """Base class for cut separation routines.

    Set ``name`` (the strategy name used in configs) and implement ``separate``.
    A fresh instance is created for every solve, so state set in ``prepare``
    never leaks between runs. Constructor keyword arguments can be set per
    config variant via ``generator_args``.

    ``placement`` decides where ``separate`` is called: ``"root"`` runs manual
    rounds on the root LP (cuts become model constraints), ``"node"`` runs in
    Gurobi's ``MIPNODE`` callback (cuts become user cuts), ``"both"`` does both,
    and ``"auto"`` means root if ``needs_tableau`` else node.
    """

    name: str = ""
    needs_tableau: bool = False
    placement: str = "auto"

    def prepare(self, problem: MatrixProblem, seed: int) -> None:
        """Called once per solve, before the first ``separate`` call."""

    @abstractmethod
    def separate(self, ctx: SeparationContext) -> Sequence[Cut]:
        """Return cuts violated by ``ctx.x`` (an empty list when none are found)."""

    def resolved_placement(self, override: str | None = None) -> str:
        placement = override or self.placement
        if placement not in PLACEMENTS:
            raise ValueError(f"{self.name}: placement must be one of {PLACEMENTS}, got {placement!r}")
        if placement == "auto":
            return "root" if self.needs_tableau else "node"
        if self.needs_tableau and placement == "node":
            raise ValueError(f"{self.name} needs the tableau, which only exists in root rounds")
        if self.needs_tableau and placement == "both":
            return "root"
        return placement
