"""Discovery of approach files and resolution of strategy names.

Strategy labels used in configs:

* ``"backend"``: Gurobi's own cuts and presolve, no user cuts (the reference).
* ``"none"``: built-in cuts and presolve off, no user cuts (the usual baseline).
* generator names joined by ``+`` (``"gmi+cover"``): built-in cuts off, only these.
* ``"backend+<names>"``: Gurobi's own cuts plus the named generators.
* a variant defined in the config's ``[variants.<label>]`` table.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from branchcut.baselines import BASELINE_GENERATORS
from branchcut.core.branching import BUILTIN_BRANCHING, BranchingRule, GurobiBranching
from branchcut.core.cuts import CutGenerator

RESERVED = ("backend", "none")
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
VARIANT_KEYS = {"cuts", "solver", "cut_options", "generator_args"}


@dataclass
class Registry:
    generators: dict[str, type[CutGenerator]] = field(default_factory=dict)
    branching: dict[str, Callable[[], BranchingRule]] = field(default_factory=dict)
    origins: dict[str, str] = field(default_factory=dict)   # "baseline", "gurobi" or a file path

    def add(self, obj, origin: str) -> None:
        name = getattr(obj, "name", "")
        if not isinstance(name, str) or not NAME_RE.match(name) or name in RESERVED:
            raise ValueError(f"{origin}: {obj.__name__}.name must be a non-reserved identifier, got {name!r}")
        if name in self.origins:
            raise ValueError(f"name {name!r} defined twice: {self.origins[name]} and {origin}")
        if isinstance(obj, type) and issubclass(obj, CutGenerator):
            self.generators[name] = obj
        else:
            self.branching[name] = obj
        self.origins[name] = origin

    def is_approach(self, name: str) -> bool:
        return self.origins.get(name) not in (None, "baseline", "gurobi")

    @property
    def approaches(self) -> list[str]:
        return sorted(n for n in self.origins if self.is_approach(n))

    def fingerprint(self, name: str) -> str | None:
        """SHA-256 of the approach file defining ``name`` (None for built-ins)."""
        if not self.is_approach(name):
            return None
        return hashlib.sha256(Path(self.origins[name]).read_bytes()).hexdigest()[:16]

    def describe(self) -> str:
        def rows(names):
            return [f"  {n:<24} {self.origins[n]}" for n in sorted(names)]
        return "\n".join(["cut generators:", *rows(self.generators),
                          "branching rules:", *rows(self.branching),
                          "special cut strategies: backend (Gurobi's own cuts), none (no cuts)"])


def _load_module(path: Path):
    name = f"_branchcut_approach_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def discover(approach_dir: str | Path = "approaches") -> Registry:
    """Built-in baselines plus every generator and branching rule in ``approach_dir/*.py``.

    Files whose names start with ``_`` are skipped (templates, helpers). Modules
    are re-executed on every call, so edits are picked up without restarting.
    """
    reg = Registry()
    for cls in BASELINE_GENERATORS.values():
        reg.add(cls, "baseline")
    for name, var_branch in BUILTIN_BRANCHING.items():
        factory = lambda name=name, vb=var_branch: GurobiBranching(name, vb)
        factory.name = name
        reg.add(factory, "gurobi")
    approach_dir = Path(approach_dir)
    for path in sorted(approach_dir.glob("*.py")) if approach_dir.is_dir() else []:
        if path.name.startswith("_"):
            continue
        module = _load_module(path)
        for obj in vars(module).values():
            if not (isinstance(obj, type) and obj.__module__ == module.__name__):
                continue
            if issubclass(obj, CutGenerator) and not inspect.isabstract(obj):
                reg.add(obj, str(path))
            elif issubclass(obj, BranchingRule) and obj is not BranchingRule:
                reg.add(obj, str(path))
    return reg


@dataclass(frozen=True)
class Strategy:
    """A resolved cut strategy label."""

    label: str
    generators: tuple[str, ...]
    builtin_cuts: bool
    generator_args: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    solver_params: Mapping[str, Any] = field(default_factory=dict)
    cut_options: Mapping[str, Any] = field(default_factory=dict)

    @property
    def cuts(self) -> str:
        tokens = (("backend",) if self.builtin_cuts else ()) + self.generators
        return "+".join(tokens) or "none"

    def build(self, registry: Registry) -> list[CutGenerator]:
        """Fresh generator instances for one solve."""
        return [registry.generators[n](**self.generator_args.get(n, {})) for n in self.generators]


def parse_cuts(spec: str, registry: Registry) -> tuple[tuple[str, ...], bool]:
    tokens = [t.strip() for t in spec.split("+")]
    if "none" in tokens and len(tokens) > 1:
        raise ValueError(f"{spec!r}: 'none' cannot be combined with other strategies")
    names = tuple(t for t in tokens if t not in RESERVED)
    unknown = [t for t in names if t not in registry.generators]
    if unknown:
        raise KeyError(f"unknown cut generator(s) {unknown} in {spec!r}; "
                       f"available: {sorted(registry.generators)} plus 'backend', 'none'")
    if len(set(names)) != len(names):
        raise ValueError(f"{spec!r} lists a generator twice")
    return names, "backend" in tokens


def resolve_strategy(label: str, registry: Registry,
                     variants: Mapping[str, Mapping[str, Any]] | None = None) -> Strategy:
    variant = dict((variants or {}).get(label, {}))
    if not variant:
        names, builtin = parse_cuts(label, registry)
        return Strategy(label, names, builtin)
    unknown = set(variant) - VARIANT_KEYS
    if unknown or "cuts" not in variant:
        raise ValueError(f"variant {label!r} needs 'cuts' and only {sorted(VARIANT_KEYS)}; got {sorted(variant)}")
    names, builtin = parse_cuts(variant["cuts"], registry)
    args = dict(variant.get("generator_args", {}))
    stray = set(args) - set(names)
    if stray:
        raise ValueError(f"variant {label!r}: generator_args for unused generators {sorted(stray)}")
    return Strategy(label, names, builtin, args, dict(variant.get("solver", {})),
                    dict(variant.get("cut_options", {})))


def resolve_branching(name: str, registry: Registry) -> BranchingRule:
    if name not in registry.branching:
        raise KeyError(f"unknown branching rule {name!r}; available: {sorted(registry.branching)}")
    return registry.branching[name]()
