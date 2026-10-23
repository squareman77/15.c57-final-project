"""Template for a branching rule. Start a new one with:

    python run.py new-approach my_rule --kind branching

Gurobi has no branching callback, so a rule is static: a VarBranch strategy plus
per-variable priorities (Gurobi branches on higher-priority fractional
variables first).
"""

import numpy as np

from branchcut.api import BranchingRule, MatrixProblem


class MyBranching(BranchingRule):
    """One-line description of the rule."""

    name = "my_branching"     # branching name used in configs/*.toml
    var_branch = -1           # -1 auto, 0 pseudo reduced cost, 1 pseudo shadow price,
                              # 2 max infeasibility, 3 strong branching

    def priorities(self, problem: MatrixProblem, seed: int):
        # return one integer per variable, or None to leave priorities to Gurobi
        return np.zeros(problem.num_vars, int)
