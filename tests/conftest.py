from pathlib import Path

import pytest

pytest.importorskip("gurobipy")

from branchcut.pipeline.registry import discover  # noqa: E402
from branchcut.solver import GurobiSolver  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
APPROACHES = ROOT / "approaches"


@pytest.fixture(scope="session")
def solver():
    return GurobiSolver()


@pytest.fixture()
def registry():
    return discover(APPROACHES)
