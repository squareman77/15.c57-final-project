"""Load a small JSON manifest of benchmark instances."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from branchcut.core.types import ProblemInstance


def load_manifest(path: str | Path) -> list[ProblemInstance]:
    """Read instances from a JSON array with name/family/source/path fields."""
    manifest_path = Path(path)
    payload: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("instance manifest must contain a JSON array")
    instances = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("each manifest entry must be a JSON object")
        instances.append(ProblemInstance(
            name=row["name"], family=row["family"], source=row["source"],
            path=row["path"], metadata=row.get("metadata", {}),
        ))
    return instances
