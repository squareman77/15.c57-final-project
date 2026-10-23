"""Gate: every approach in approaches/ must pass validation (run before merging a new one)."""

import pytest

from branchcut.pipeline.registry import discover
from branchcut.pipeline.validation import validate

from conftest import APPROACHES

NAMES = discover(APPROACHES).approaches


@pytest.mark.parametrize("name", NAMES)
def test_approach_passes_validation(name, registry, solver):
    (report,) = validate([name], registry, solver)
    assert report.passed, f"\n{report}"


@pytest.mark.parametrize("name", ["gmi", "cover"])
def test_baselines_pass_validation(name, registry, solver):
    (report,) = validate([name], registry, solver)
    assert report.passed, f"\n{report}"
