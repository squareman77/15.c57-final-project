"""Problem representation, MPS round trip, cuts, configs and report math."""

import numpy as np
import pytest

from branchcut.core.cuts import Cut
from branchcut.pipeline.config import load_config
from branchcut.pipeline.registry import parse_cuts, resolve_strategy
from branchcut.pipeline.report import gap_closed, sgm
from branchcut.scenarios import build_instances
from branchcut.scenarios.generators import FAMILIES, generate
from branchcut.solver import RunSpec


@pytest.mark.parametrize("family, params", [
    ("knapsack", dict(n=12, m=3)),
    ("set_cover", dict(rows=10, cols=15)),
    ("facility_location", dict(facilities=4, customers=6, strong_linking=True)),
])
def test_mps_roundtrip(solver, tmp_path, family, params):
    direct = FAMILIES[family](seed=3, **params)
    loaded = solver.load_problem(generate(family, 3, tmp_path, **params))
    assert loaded.maximize == direct.maximize
    assert loaded.senses == direct.senses
    for attr in ("objective", "rhs", "lb", "ub", "is_integer"):
        np.testing.assert_array_equal(getattr(loaded, attr), getattr(direct, attr))
    np.testing.assert_array_equal(loaded.dense_rows(), direct.dense_rows())


def test_knapsack_generator_is_stable(solver, tmp_path):
    # regression: the instance used throughout development has optimum 1609
    r = solver.solve(RunSpec(generate("knapsack", 7, tmp_path, n=60, m=8), builtin_cuts=True))
    assert r.objective == 1609


def test_cut_from_dense_and_violation():
    cut = Cut.from_dense(np.array([1.0, 0.0, 2.0]), 3.0, ">=")
    assert cut.coefficients == {0: -1.0, 2: -2.0} and cut.rhs == -3.0
    assert cut.violation(np.array([1.0, 0.0, 0.0])) > 0
    np.testing.assert_allclose(cut.violation(np.array([[0, 0, 2], [1, 0, 1]], float)), [-1.0, 0.0])
    with pytest.raises(ValueError):
        Cut.from_dense([1.0], 1.0, "==")


def test_strategy_parsing(registry):
    assert parse_cuts("gmi+cover", registry) == (("gmi", "cover"), False)
    assert parse_cuts("backend+cmir", registry) == (("cmir",), True)
    assert parse_cuts("none", registry) == ((), False)
    with pytest.raises(ValueError):
        parse_cuts("none+gmi", registry)
    with pytest.raises(KeyError):
        parse_cuts("not_a_cut", registry)
    variant = resolve_strategy("deep", registry, {"deep": {"cuts": "gmi", "cut_options": {"root_rounds": 30},
                                                            "generator_args": {"gmi": {"min_fractionality": 0.1}}}})
    assert variant.cuts == "gmi" and variant.cut_options["root_rounds"] == 30
    assert variant.build(registry)[0].min_fractionality == 0.1
    with pytest.raises(ValueError):
        resolve_strategy("bad", registry, {"bad": {"cuts": "gmi", "generator_args": {"cover": {}}}})


def test_config_validation(tmp_path):
    good = tmp_path / "good.toml"
    good.write_text('name = "x"\nstrategies = ["backend", "none"]\n[[scenarios]]\nfamily = "knapsack"\n')
    cfg = load_config(good)
    assert cfg.baseline == "none" and cfg.time_limit == 60
    bad = tmp_path / "bad.toml"
    bad.write_text('name = "x"\nstrategies = ["none"]\nstrategy = []\n[[scenarios]]\nfamily = "knapsack"\n')
    with pytest.raises(ValueError, match="unknown keys"):
        load_config(bad)
    with pytest.raises(ValueError, match="unknown keys"):
        build_instances([{"family": "knapsack", "parms": {}}], tmp_path)


def test_report_math():
    assert sgm([1.0, 1.0], 1.0) == pytest.approx(1.0)
    assert sgm([0.0, 3.0], 1.0) == pytest.approx(1.0)        # exp(mean(log 1, log 4)) - 1
    assert gap_closed(10.0, 8.0, 6.0) == pytest.approx(0.5)  # maximization
    assert gap_closed(4.0, 5.0, 6.0) == pytest.approx(0.5)   # minimization
    assert gap_closed(5.0, 5.0, 5.0) is None
