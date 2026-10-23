# Branch-and-Cut Experiments

Code for studying how branching rules and cutting-plane strategies affect the
performance of integer-programming solvers across different problem structures.

## Project layout

```text
src/branchcut/
  core/          Solver-independent problem, node, and result types
  strategies/    Branching-rule and cut-generator interfaces and implementations
  backends/      Adapters to LP/MIP solver libraries
  scenarios/    Problem families and instance loading
  experiments/  Experiment configuration, execution, and result export
configs/         Reproducible experiment matrices
data/            Downloaded or generated instances (not committed)
results/         Experiment outputs (not committed)
```

The central design goal is to keep algorithms interchangeable. An experiment
should select a backend, branching rule, cut strategy, and set of scenarios
without embedding those choices in the branch-and-bound loop.

## Planned first milestones

1. Choose a solver backend and define what solver capabilities the study needs.
2. Implement a baseline branch-and-bound run with a documented default branch
   rule and no custom cuts; record the backend's own cuts separately.
3. Add branching rules and cut generators behind the strategy interfaces.
4. Define scenario groups (for example, set covering, knapsack, facility
   location, and selected MIPLIB instances) and run a fixed experiment matrix.
5. Compare runtime, explored nodes, LP solves, cuts added, and final solver
   status, with solver version, parameters, seed, and time limit recorded.

Gomory cuts require care: they are derived from an LP tableau and should only be
implemented where the chosen backend exposes the needed tableau information,
or via a dedicated LP implementation. The backend interface should make this
capability explicit instead of silently treating every solver as compatible.

## Development

Python 3.11 or newer is expected. Install the package in editable mode:

```bash
python -m pip install -e .
```

The initial scaffold defines interfaces and data structures only. It does not
yet solve optimization models; select and add a solver backend before running
experiments.

## Data sources

- [MIPLIB](https://miplib.zib.de/)
- [Lehigh mixed-integer programming instances](https://coral.ise.lehigh.edu/data-sets/mixed-integer-instances/)

Check each source's terms and cite the selected instances in project reports.
