"""Records shared by scenarios, the solver and the benchmark pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Mapping

STATUSES = ("optimal", "infeasible", "unbounded", "inf_or_unbd", "time_limit",
            "node_limit", "interrupted", "error", "unknown")


@dataclass(frozen=True)
class Instance:
    """A named instance file; parsing belongs to the solver."""

    name: str
    family: str
    source: str
    path: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """Normalized measurements for one solve."""

    status: str
    objective: float | None = None
    best_bound: float | None = None
    gap: float | None = None
    root_bound: float | None = None          # root LP objective after the last cut round
    runtime: float = 0.0                     # wall clock, including root rounds and separation
    work: float | None = None                # Gurobi work units (deterministic, solver only)
    nodes: int = 0
    simplex_iterations: float = 0.0
    cuts_added: int = 0                      # root cuts as constraints + user cuts Gurobi applied
    root_cuts_added: int = 0
    user_cuts_applied: int = 0
    cuts_generated: dict[str, int] = field(default_factory=dict)
    separation_seconds: dict[str, float] = field(default_factory=dict)
    backend_cuts: dict[str, int] = field(default_factory=dict)
    root_bound_history: list[float] = field(default_factory=list)
    tableau_skipped: int = 0
    parameters: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    cut_log: list[dict[str, Any]] | None = None
    solution: Any = None

    def to_record(self) -> dict[str, Any]:
        """JSON-serializable fields (drops ``cut_log`` and ``solution``)."""
        return {f.name: getattr(self, f.name) for f in fields(self)
                if f.name not in ("cut_log", "solution")}
