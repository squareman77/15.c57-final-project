"""Solver-independent matrix view of a mixed-integer linear program, and an MPS writer."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True, eq=False)
class MatrixProblem:
    """``max/min objective @ x`` s.t. ``row_i @ x  sense_i  rhs_i`` and ``lb <= x <= ub``.

    Rows are stored sparsely as ``(indices, values)`` so that large instances can
    be inspected without forming a dense matrix. Senses are ``"<"``, ``">"`` or
    ``"="``.
    """

    objective: np.ndarray
    rows: tuple[tuple[np.ndarray, np.ndarray], ...]
    senses: tuple[str, ...]
    rhs: np.ndarray
    lb: np.ndarray
    ub: np.ndarray
    is_integer: np.ndarray
    maximize: bool = False

    @classmethod
    def from_dense(cls, objective, A, senses: Sequence[str], rhs, lb, ub, is_integer,
                   maximize: bool = False) -> MatrixProblem:
        A = np.asarray(A, float)
        rows = []
        for row in A:
            nz = np.flatnonzero(row)
            rows.append((nz, row[nz]))
        return cls(np.asarray(objective, float), tuple(rows), tuple(senses),
                   np.asarray(rhs, float), np.asarray(lb, float), np.asarray(ub, float),
                   np.asarray(is_integer, bool), maximize)

    @property
    def num_vars(self) -> int:
        return len(self.objective)

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def is_binary(self) -> np.ndarray:
        return self.is_integer & (self.lb >= 0) & (self.ub <= 1)

    def dense_rows(self) -> np.ndarray:
        A = np.zeros((self.num_rows, self.num_vars))
        for i, (idx, val) in enumerate(self.rows):
            A[i, idx] = val
        return A

    def less_equal_rows(self) -> Iterator[tuple[np.ndarray, np.ndarray, float]]:
        """Yield every row as ``val @ x[idx] <= rhs``; ``=`` rows yield both directions."""
        for (idx, val), sense, rhs in zip(self.rows, self.senses, self.rhs):
            if sense in ("<", "="):
                yield idx, val, float(rhs)
            if sense in (">", "="):
                yield idx, -val, -float(rhs)

    def is_feasible(self, points: np.ndarray, tol: float = 1e-6) -> np.ndarray:
        """Feasibility mask for a stack of points with shape ``(k, num_vars)``."""
        points = np.atleast_2d(points)
        ok = np.all((points >= self.lb - tol) & (points <= self.ub + tol), axis=1)
        integral = np.abs(points[:, self.is_integer] - np.round(points[:, self.is_integer]))
        ok &= np.all(integral <= tol, axis=1)
        for idx, val, rhs in self.less_equal_rows():
            ok &= points[:, idx] @ val <= rhs + tol
        return ok


def _num(value: float) -> str:
    return f"{value:.17g}"


def write_mps(problem: MatrixProblem, path: str | Path, name: str = "problem") -> None:
    """Write ``problem`` as free-format MPS (variables ``x<j>``, rows ``r<i>``)."""
    columns: list[list[tuple[int, float]]] = [[] for _ in range(problem.num_vars)]
    for i, (idx, val) in enumerate(problem.rows):
        for j, v in zip(idx, val):
            if v != 0:
                columns[j].append((i, v))
    kind = {"<": "L", ">": "G", "=": "E"}
    lines = [f"NAME {name}"]
    if problem.maximize:
        lines += ["OBJSENSE", "    MAX"]
    lines += ["ROWS", " N obj"] + [f" {kind[s]} r{i}" for i, s in enumerate(problem.senses)]
    lines.append("COLUMNS")
    in_int = False
    for j in range(problem.num_vars):
        if bool(problem.is_integer[j]) != in_int:
            lines.append("    MARKER 'MARKER' " + ("'INTEND'" if in_int else "'INTORG'"))
            in_int = not in_int
        lines.append(f"    x{j} obj {_num(problem.objective[j])}")
        lines += [f"    x{j} r{i} {_num(v)}" for i, v in columns[j]]
    if in_int:
        lines.append("    MARKER 'MARKER' 'INTEND'")
    lines.append("RHS")
    lines += [f"    rhs r{i} {_num(b)}" for i, b in enumerate(problem.rhs) if b != 0]
    lines.append("BOUNDS")
    for j in range(problem.num_vars):
        lo, up = problem.lb[j], problem.ub[j]
        if problem.is_integer[j] and lo == 0 and up == 1:
            lines.append(f" BV bnd x{j}")
            continue
        if lo == -np.inf and up == np.inf:
            lines.append(f" FR bnd x{j}")
            continue
        if lo == -np.inf:
            lines.append(f" MI bnd x{j}")
        elif lo != 0:
            lines.append(f" LO bnd x{j} {_num(lo)}")
        if up != np.inf:
            lines.append(f" UP bnd x{j} {_num(up)}")
        elif problem.is_integer[j]:
            lines.append(f" PL bnd x{j}")
    lines.append("ENDATA")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
