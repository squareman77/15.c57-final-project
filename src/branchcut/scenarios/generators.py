"""Random instance families, written to MPS so every source is loaded the same way."""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np

from branchcut.core.problem import MatrixProblem, write_mps
from branchcut.core.types import Instance


def multidimensional_knapsack(n: int = 30, m: int = 5, tightness: float = 0.5, *,
                              seed: int) -> MatrixProblem:
    """``max c'x  s.t.  A x <= b,  x binary`` with integer data."""
    rng = np.random.default_rng(seed)
    A = rng.integers(5, 60, size=(m, n)).astype(float)
    c = (A.sum(axis=0) / m + rng.integers(1, 30, size=n)).round()
    b = np.floor(tightness * A.sum(axis=1))
    return MatrixProblem.from_dense(c, A, ["<"] * m, b, np.zeros(n), np.ones(n),
                                    np.ones(n, bool), maximize=True)


def set_cover(rows: int = 50, cols: int = 100, density: float = 0.05, max_cost: int = 100, *,
              seed: int) -> MatrixProblem:
    """``min c'x  s.t.  A x >= 1,  x binary``; every row is covered by at least two columns.

    Costs are uniform on ``1..max_cost``; small ``max_cost`` (e.g. 1-5) gives harder instances.
    """
    rng = np.random.default_rng(seed)
    A = (rng.random((rows, cols)) < density).astype(float)
    for i in range(rows):
        while A[i].sum() < 2:
            A[i, rng.integers(cols)] = 1.0
    cost = rng.integers(1, max_cost + 1, size=cols).astype(float)
    return MatrixProblem.from_dense(cost, A, [">"] * rows, np.ones(rows), np.zeros(cols),
                                    np.ones(cols), np.ones(cols, bool))


def facility_location(facilities: int = 10, customers: int = 30, capacity_ratio: float = 3.0,
                      strong_linking: bool = False, *, seed: int) -> MatrixProblem:
    """Capacitated facility location with binary opening ``y_i`` and continuous ``x_ij``.

    ``min sum f_i y_i + sum c_ij x_ij``  s.t.  ``sum_i x_ij = 1`` (each customer
    served), ``sum_j d_j x_ij <= u_i y_i`` (capacity), and optionally
    ``x_ij <= y_i``. Variables are ``y`` first, then ``x`` row-major by facility.
    """
    rng = np.random.default_rng(seed)
    F, C = facilities, customers
    fac, cust = rng.random((F, 2)), rng.random((C, 2))
    demand = rng.integers(5, 35, size=C).astype(float)
    capacity = rng.integers(10, 160, size=F).astype(float)
    capacity = np.ceil(capacity * capacity_ratio * demand.sum() / capacity.sum())
    fixed = np.round(capacity * rng.uniform(2, 4, size=F))
    dist = np.linalg.norm(fac[:, None, :] - cust[None, :, :], axis=2)
    serve = np.round(10 * dist * demand[None, :])

    n = F + F * C
    xcol = lambda i, j: F + i * C + j
    rows, senses, rhs = [], [], []

    def add(entries: dict[int, float], sense: str, b: float) -> None:
        row = np.zeros(n)
        for j, v in entries.items():
            row[j] = v
        rows.append(row)
        senses.append(sense)
        rhs.append(b)

    for j in range(C):
        add({xcol(i, j): 1.0 for i in range(F)}, "=", 1.0)
    for i in range(F):
        add({**{xcol(i, j): demand[j] for j in range(C)}, i: -capacity[i]}, "<", 0.0)
    if strong_linking:
        for i in range(F):
            for j in range(C):
                add({xcol(i, j): 1.0, i: -1.0}, "<", 0.0)
    objective = np.concatenate([fixed, serve.ravel()])
    is_integer = np.concatenate([np.ones(F, bool), np.zeros(F * C, bool)])
    return MatrixProblem.from_dense(objective, np.array(rows), senses, rhs, np.zeros(n),
                                    np.ones(n), is_integer)


FAMILIES = {
    "knapsack": multidimensional_knapsack,
    "set_cover": set_cover,
    "facility_location": facility_location,
}
PREFIX = {"knapsack": "mkp", "set_cover": "scp", "facility_location": "cfl"}
ABBREV = {"tightness": "t", "rows": "r", "cols": "c", "density": "d", "max_cost": "mc",
          "facilities": "f", "customers": "c", "capacity_ratio": "cap", "strong_linking": "sl"}


def instance_name(family: str, seed: int, params: dict) -> str:
    """Short, deterministic name such as ``mkp_n60_m8_s7`` (parameters in signature order)."""
    order = list(inspect.signature(FAMILIES[family]).parameters)
    tags = [f"{ABBREV.get(k, k)}{int(v) if isinstance(v, bool) else v}"
            for k, v in sorted(params.items(), key=lambda kv: order.index(kv[0]))]
    return "_".join([PREFIX[family], *tags, f"s{seed}"])


def generate(family: str, seed: int, directory: str | Path, **params) -> Instance:
    """Generate one instance of ``family``, write it to ``directory`` and return it."""
    if family not in FAMILIES:
        raise KeyError(f"unknown family {family!r}; choose from {sorted(FAMILIES)}")
    problem = FAMILIES[family](seed=seed, **params)
    name = instance_name(family, seed, params)
    path = Path(directory) / f"{name}.mps"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_mps(problem, path, name)
    return Instance(name, family, "generated", str(path), dict(seed=seed, **params))
