"""Instances from existing files: glob patterns or a JSON manifest."""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

from branchcut.core.types import Instance

SUFFIXES = (".gz", ".bz2", ".mps", ".lp")


def _stem(path: Path) -> str:
    name = path.name
    for suffix in SUFFIXES:
        name = name.removesuffix(suffix)
    return name


def from_files(patterns, family: str = "files") -> list[Instance]:
    paths = sorted({Path(p) for pattern in patterns for p in glob.glob(str(pattern))})
    if not paths:
        raise FileNotFoundError(f"no instance files match {list(patterns)}")
    return [Instance(_stem(p), family, "file", str(p)) for p in paths]


def load_manifest(path: str | Path) -> list[Instance]:
    """Read instances from a JSON array of ``{name, family, source, path[, metadata]}``."""
    payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("instance manifest must contain a JSON array")
    instances = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("each manifest entry must be a JSON object")
        instances.append(Instance(name=row["name"], family=row["family"], source=row["source"],
                                  path=row["path"], metadata=row.get("metadata", {})))
    return instances
