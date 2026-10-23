"""Experiment configs (TOML). See ``configs/README.md`` for every key."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from branchcut.pipeline.registry import Registry, resolve_branching, resolve_strategy


@dataclass
class ExperimentConfig:
    name: str
    strategies: list[str]
    scenarios: list[dict[str, Any]]
    description: str = ""
    branching: list[str] = field(default_factory=lambda: ["default"])
    seeds: list[int] = field(default_factory=lambda: [0])
    time_limit: float | None = 60.0
    baseline: str | None = "none"
    reference: str | None = "backend"
    validate: bool = True
    keep_logs: bool = False
    solver: dict[str, Any] = field(default_factory=dict)
    cut_options: dict[str, Any] = field(default_factory=dict)
    variants: dict[str, dict[str, Any]] = field(default_factory=dict)
    path: str | None = None

    def check(self, registry: Registry) -> None:
        """Resolve every strategy and branching rule now, so typos fail before any solve."""
        for label in self.strategies:
            resolve_strategy(label, registry, self.variants)
        for name in self.branching:
            resolve_branching(name, registry)


FIELDS = set(ExperimentConfig.__dataclass_fields__) - {"path"}


def load_config(path: str | Path) -> ExperimentConfig:
    path = Path(path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    unknown = set(data) - FIELDS
    if unknown:
        raise ValueError(f"{path}: unknown keys {sorted(unknown)}; allowed: {sorted(FIELDS)}")
    missing = {"name", "strategies", "scenarios"} - set(data)
    if missing:
        raise ValueError(f"{path}: missing required keys {sorted(missing)}")
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", data["name"]):
        raise ValueError(f"{path}: name must be letters, digits, '_' or '-'")
    if data.get("time_limit") == 0:
        data["time_limit"] = None                   # 0 means no limit
    for key in ("baseline", "reference"):
        if data.get(key) == "":
            data[key] = None                        # "" disables it (TOML has no null)
    cfg = ExperimentConfig(**data, path=str(path))
    if len(set(cfg.strategies)) != len(cfg.strategies):
        raise ValueError(f"{path}: duplicate strategies")
    for key in ("baseline", "reference"):
        value = getattr(cfg, key)
        if value is None or value in cfg.strategies:
            continue
        if key in data:
            raise ValueError(f"{path}: {key} {value!r} is not one of the strategies")
        setattr(cfg, key, None)                     # default not in this experiment: disable it
    return cfg
