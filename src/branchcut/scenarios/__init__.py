"""Instance sources: generated families, MIPLIB, files and manifests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from branchcut.core.types import Instance
from branchcut.scenarios import miplib, sources
from branchcut.scenarios.generators import FAMILIES, generate

SOURCES = (*FAMILIES, "miplib", "files", "manifest")


def build_instances(specs: Iterable[Mapping[str, Any]], data_dir: str | Path = "data") -> list[Instance]:
    """Resolve the ``[[scenarios]]`` entries of a config into instances."""
    data_dir = Path(data_dir)
    instances: list[Instance] = []
    for spec in specs:
        spec = dict(spec)
        family = spec.pop("family", None)
        if family in FAMILIES:
            count, seed, params = spec.pop("count", 1), spec.pop("seed", 0), spec.pop("params", {})
            instances += [generate(family, s, data_dir / "generated" / family, **params)
                          for s in range(seed, seed + count)]
        elif family == "miplib":
            names = list(spec.pop("names", []))
            if "list" in spec:
                names += miplib.benchmark_names(spec.pop("list"))
            limit = spec.pop("limit", None)
            directory = spec.pop("directory", data_dir / "miplib")
            instances += [miplib.instance(n, directory) for n in names[:limit]]
        elif family == "files":
            instances += sources.from_files(spec.pop("paths"), spec.pop("label", "files"))
        elif family == "manifest":
            instances += sources.load_manifest(spec.pop("path"))
        else:
            raise ValueError(f"unknown scenario family {family!r}; choose from {list(SOURCES)}")
        if spec:
            raise ValueError(f"unknown keys {sorted(spec)} in scenario {family!r}")
    seen: set[str] = set()
    for inst in instances:
        if inst.name in seen:
            raise ValueError(f"duplicate instance name {inst.name!r}")
        seen.add(inst.name)
    return instances
