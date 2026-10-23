"""Serializable experiment matrix definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    backend: str
    instances: tuple[str, ...]
    branching_rules: tuple[str, ...]
    cut_strategies: tuple[str, ...]
    parameters: Mapping[str, Any] = field(default_factory=dict)
    seed: int = 0
    time_limit_seconds: float = 300.0

    def combinations(self):
        """Yield the full instance × branching × cut comparison matrix."""
        for instance in self.instances:
            for branching in self.branching_rules:
                for cuts in self.cut_strategies:
                    yield instance, branching, cuts
