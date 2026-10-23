"""Common immutable records used by strategies, backends, and experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SolveStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    TIME_LIMIT = "time_limit"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProblemInstance:
    """A named instance reference; model parsing belongs to a backend/loader."""

    name: str
    family: str
    source: str
    path: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SolverCapabilities:
    """Features that strategies may require from a solver backend."""

    lp_tableau: bool = False
    add_linear_constraints: bool = False
    callback_branching: bool = False
    callback_cuts: bool = False


@dataclass(frozen=True)
class RunMetrics:
    """Comparable measurements returned by a backend for one solve."""

    runtime_seconds: float
    explored_nodes: int | None = None
    lp_solves: int | None = None
    cuts_added: int | None = None
    objective_value: float | None = None
    best_bound: float | None = None
    relative_gap: float | None = None


@dataclass(frozen=True)
class SolveResult:
    status: SolveStatus
    metrics: RunMetrics
    solver_name: str
    solver_version: str
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
