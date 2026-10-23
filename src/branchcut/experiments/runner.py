"""Orchestration for reproducible backend runs."""

from __future__ import annotations

from branchcut.backends.base import SolverBackend
from branchcut.core.types import ProblemInstance, SolveResult
from branchcut.experiments.config import ExperimentConfig


def run_experiment(
    config: ExperimentConfig,
    *,
    backend: SolverBackend,
    instances: dict[str, ProblemInstance],
) -> list[tuple[str, str, str, SolveResult]]:
    """Run every configured combination in deterministic order."""
    results = []
    for instance_name, branching, cuts in config.combinations():
        instance = instances[instance_name]
        result = backend.solve(
            instance,
            branching=branching,
            cuts=cuts,
            parameters={
                **config.parameters,
                "seed": config.seed,
                "time_limit_seconds": config.time_limit_seconds,
            },
        )
        results.append((instance_name, branching, cuts, result))
    return results
