"""Template for a cut generator. Start a new one with:

    python run.py new-approach my_idea            # creates approaches/my_idea.py

Files in approaches/ whose names start with "_" are not loaded.
"""

import numpy as np

from branchcut.api import Cut, CutGenerator, MatrixProblem, SeparationContext


class MyCuts(CutGenerator):
    """One-line description of the cut family (shown in reports)."""

    name = "my_cuts"          # strategy name used in configs/*.toml
    needs_tableau = False     # True: run in root LP rounds with ctx.tableau available
    placement = "auto"        # "auto" | "root" | "node" | "both"

    def __init__(self, min_violation: float = 1e-4):
        # keyword arguments can be set per config variant via generator_args
        self.min_violation = min_violation

    def prepare(self, problem: MatrixProblem, seed: int) -> None:
        # once per solve: cache the rows you will scan, set up an RNG, ...
        self.rng = np.random.default_rng(seed)
        self.rows = list(problem.less_equal_rows())     # each row as a @ x[idx] <= rhs

    def separate(self, ctx: SeparationContext) -> list[Cut]:
        # ctx.x        relaxation point to cut off
        # ctx.problem  original rows (cuts from them are globally valid)
        # ctx.tableau  root simplex tableau (needs_tableau generators in root rounds only)
        # ctx.where    "root" or "node"; ctx.round / ctx.node_count
        cuts = []
        for idx, a, rhs in self.rows:
            coef = np.zeros(ctx.problem.num_vars)
            # ... derive an inequality  coef @ x <= beta  valid for all integer points ...
            # cut = Cut.from_dense(coef, beta, "<=", family=self.name)
            # if cut.violation(ctx.x) > self.min_violation:
            #     cuts.append(cut)
        return cuts
