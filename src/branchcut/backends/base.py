"""Solver backend contract; concrete integrations live in this package."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from branchcut.core.types import ProblemInstance, SolveResult, SolverCapabilities


class SolverBackend(ABC):
    name: str

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> SolverCapabilities: ...

    @abstractmethod
    def solve(
        self,
        instance: ProblemInstance,
        *,
        branching: str,
        cuts: str,
        parameters: Mapping[str, Any],
    ) -> SolveResult:
        """Solve one instance and return normalized metrics."""
