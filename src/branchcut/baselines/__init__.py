"""Standard cut families that approaches are benchmarked against."""

from branchcut.baselines.cover import ExtendedCoverCuts
from branchcut.baselines.gmi import GomoryMixedIntegerCuts

BASELINE_GENERATORS = {cls.name: cls for cls in (GomoryMixedIntegerCuts, ExtendedCoverCuts)}
