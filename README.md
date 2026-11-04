# Branch-and-Cut Experiments

A suite for studying how cutting planes and branching rules affect the performance of an integer-programming solver across problem structures. Approaches are written as small Python files; a fixed pipeline validates them, benchmarks them against baselines on Gurobi, and reports the results.

## What you edit, and what you don't

```text
approaches/         EDIT  one file per approach: cut generators and branching rules
  _template_cuts.py         copied by `python run.py new-approach NAME`
  _template_branching.py    copied by `python run.py new-approach NAME --kind branching`
  cmir.py                   example cut generator (c-MIR on single binary rows)
  objective_priority.py     example branching rule
configs/            EDIT  experiments as TOML: instances × strategies × branching × seeds
notebooks/workbench.ipynb  interactive: validate, benchmark and explore results

src/branchcut/      FIXED  the pipeline
  api.py                    the only module approach files import from
  core/                     problem matrix and MPS writer, simplex tableau, Cut / CutGenerator / BranchingRule
  baselines/                standard cut families to compare against: gmi, cover
  solver.py                 Gurobi runs: built-in cuts off/on, root cut rounds, node callback, metrics
  scenarios/                knapsack, set cover, facility location generators; MIPLIB; files; manifests
  pipeline/                 registry (discovery), config, validation gate, benchmark runner, report
  cli.py                    `python run.py ...`
tests/              FIXED  pipeline tests, plus a gate that validates every file in approaches/
data/  results/            instances and outputs (git-ignored)
```

Files in `approaches/` are discovered automatically. Every `CutGenerator` or `BranchingRule` subclass defined there becomes available by its `name` in configs, so adding an approach never requires touching the pipeline.

## Quick start

Python 3.11+, `numpy`, and `gurobipy` with a license. You can run everything without installing:

```bash
python run.py list                          # approaches, baselines, branching rules, configs
python run.py validate                      # correctness checks for every approach
python run.py bench configs/smoke.toml      # about 20 s; writes results/smoke/<timestamp>/
python run.py report results/smoke          # re-print the latest summary
python -m pytest                            # pipeline tests and the approach gate
```

Alternatively, `python -m pip install -e ".[test]"` installs the package and a `branchcut` command that works like `python run.py`.

## Workflow for a new approach

1. `python run.py new-approach my_idea` creates `approaches/my_idea.py` from the template.
2. Implement `separate(ctx)` to return `Cut` objects violated by `ctx.x`. See [approaches/README.md](approaches/README.md) for the interface, where generators run, and how to use the tableau.
3. `python run.py validate my_idea`, or section 1 of the workbench, until every check passes.
4. Add `"my_idea"` (or combinations like `"gmi+my_idea"` and `"backend+my_idea"`) to a config's `strategies`.
5. `python run.py bench configs/<config>.toml`, then read `results/<name>/<timestamp>/summary.md`.
6. Run `python -m pytest` before merging: `tests/test_approaches.py` validates every approach in the folder.

## Strategies and baselines

| strategy label | meaning |
|---|---|
| `backend` | Gurobi with its own cuts and presolve (reference for correctness) |
| `none` | `Cuts=0`, `Presolve=0`, `PreCrush=1`, and no user cuts (usual baseline) |
| `gmi`, `cover`, any approach name | built-in cuts off; only the named generators |
| `a+b` | built-in cuts off; generators `a` and `b` together |
| `backend+a` | Gurobi's own cuts plus generator `a` |
| a `[variants.<label>]` entry | any of the above with its own `cut_options`, `solver` parameters or constructor `generator_args` |

Branching: `default`, `pseudo_reduced_cost`, `pseudo_shadow_price`, `max_infeasibility` (alias `most_fractional`), `strong`, or any branching-rule approach.

When built-in cuts are off, every run checks that the parameters took effect and parses Gurobi's "Cutting planes" log section. Any leaked built-in cut appears in `backend_cuts`, and validation fails.

## What is measured

Each run records status, objective, best bound, gap, runtime (wall clock, including root cut rounds and Python separation), Gurobi work units (deterministic solver effort), nodes, simplex iterations, the root LP bound after cuts, the LP relaxation bound, cuts generated and applied per generator, separation time, Gurobi's own cuts by family, and every parameter applied. Each results directory also stores the config, solver and Python versions, the git commit, and a hash of every approach file used.

`summary.md` reports, per strategy and branching rule:
- solved, time-limit, error and **wrong** counts (wrong = an optimum or bound that contradicts the reference, which means an invalid cut)
- shifted geometric means of time, nodes and work, with ratios against the baseline on matched runs
- mean root gap closed
- cuts added and separation-time share

It also breaks results down by family and by instance. Definitions are at the bottom of every summary.

## Commands

| command | what it does |
|---|---|
| `list` | registered cut generators and branching rules (with source file), families, configs |
| `validate [NAME ...]` | correctness checks (default: every approach); exit code 1 on failure |
| `bench CONFIG [--dry-run] [--only LABEL ...] [--resume DIR] [--skip-validation]` | validate the approaches used, then run the matrix |
| `report DIR` | rebuild `summary.md` and `runs.csv` for a run, or for the latest run of an experiment |
| `fetch-miplib NAME ... \| --benchmark-list data/benchmark-v2.test [--limit N]` | download MIPLIB 2017 instances into `data/miplib/` |
| `new-approach NAME [--kind cuts\|branching]` | scaffold a new approach file |

## Design notes and limits

- **Gurobi only.** The suite targets one solver, so there is no backend abstraction. Gurobi's matrix API needs scipy; the code uses the scalar API so a broken scipy install doesn't matter.
- **Branching rules are static.** Gurobi has no branching callback, so a rule is a `VarBranch` strategy plus per-variable `BranchPriority` values.
- **Tableau access.** `core/tableau.py` rebuilds the tableau from the optimal basis of the root LP. It exists only in root rounds and is dense, so it suits up to a few thousand rows. Larger LPs skip tableau-based generators (`max_tableau_size`), and the skip is recorded.
- **Not reported by Gurobi:** node depth in callbacks (contexts have `node_count` instead) and LP solve counts (simplex iterations are recorded instead).
- **Benchmark hygiene.** Use `Threads = 1` and several seeds for comparisons. Wall time includes Python overhead, so also look at work units and nodes.

## Data sources

- [MIPLIB 2017](https://miplib.zib.de/) (`data/benchmark-v2.test` lists the benchmark set)
- [Lehigh mixed-integer programming instances](https://coral.ise.lehigh.edu/data-sets/mixed-integer-instances/) (load with a `files` scenario)

Check each source's terms and cite the selected instances in project reports.
