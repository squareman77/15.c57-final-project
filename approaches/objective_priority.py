"""Example approach: branch first on integer variables with the largest |objective coefficient|."""

import numpy as np

from branchcut.api import BranchingRule, MatrixProblem


class ObjectivePriority(BranchingRule):
    """Priority = rank of |c_j| among integer variables."""

    name = "objective_priority"

    def priorities(self, problem: MatrixProblem, seed: int):
        rank = np.argsort(np.argsort(np.abs(problem.objective)))
        return np.where(problem.is_integer, rank, 0)
