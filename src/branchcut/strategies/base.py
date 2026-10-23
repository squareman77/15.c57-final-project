"""Interfaces for strategies selected by an experiment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


class NodeView(Protocol):
    """Read-only information about an active search node."""

    @property
    def depth(self) -> int: ...

    @property
    def relaxation_objective(self) -> float | None: ...


@dataclass(frozen=True)
class BranchDecision:
    variable: int
    value: float
    reason: str = ""


@dataclass(frozen=True)
class LinearCut:
    """Linear inequality sum(coefficients[i] * x[i]) <= rhs."""

    coefficients: Mapping[int, float]
    rhs: float
    name: str = ""
    family: str = "user"


class BranchingRule(ABC):
    name: str

    @abstractmethod
    def choose(self, node: NodeView, fractional_variables: Sequence[int]) -> BranchDecision:
        """Choose a fractional variable and its current LP value."""


class CutGenerator(ABC):
    name: str
    required_capabilities: frozenset[str] = frozenset()

    @abstractmethod
    def separate(self, node: NodeView) -> Sequence[LinearCut]:
        """Return valid cuts violated by the current relaxation, if any."""


class StrategyConfig(Protocol):
    """Marker protocol for serializable strategy settings."""

    def as_dict(self) -> Mapping[str, Any]: ...
