# Approaches

Every `.py` file here, except those starting with `_`, is loaded by the pipeline. Each `CutGenerator` or `BranchingRule` subclass defined in a file is registered under its `name` and can be used in any config. Import only from `branchcut.api`.

```bash
python run.py new-approach my_idea                    # cut generator from _template_cuts.py
python run.py new-approach my_rule --kind branching   # branching rule from _template_branching.py
python run.py validate my_idea
```

## Cut generators

```python
from branchcut.api import Cut, CutGenerator, SeparationContext

class MyCuts(CutGenerator):
    name = "my_cuts"          # label in configs; letters, digits, _ and -
    needs_tableau = False     # True: called in root LP rounds with ctx.tableau
    placement = "auto"        # "auto" | "root" | "node" | "both"

    def prepare(self, problem, seed): ...         # once per solve (optional)
    def separate(self, ctx: SeparationContext) -> list[Cut]: ...
```

**What `separate` receives** (`SeparationContext`):

| field | meaning |
|---|---|
| `ctx.x` | relaxation point to cut off (numpy array indexed like the model's variables) |
| `ctx.problem` | `MatrixProblem` of the original model: `objective`, `rows` (sparse `(idx, val)`), `senses`, `rhs`, `lb`, `ub`, `is_integer`, `is_binary`, `maximize`, `less_equal_rows()` (each row as `val @ x[idx] <= rhs`), `dense_rows()` |
| `ctx.tableau` | `SimplexTableau` of the current root LP, cuts from earlier rounds included (root rounds and `needs_tableau` only, otherwise `None`): `fractional_rows()`, `rows[r]`, `value[r]`, `nonbasic_integer`, `to_x(g, rhs)` maps `g @ y >= rhs` to `alpha @ x >= beta` |
| `ctx.where` | `"root"` (manual LP rounds before branching) or `"node"` (Gurobi `MIPNODE` callback, including node 0) |
| `ctx.round`, `ctx.node_count` | root round number; nodes explored so far |
| `ctx.fractional()` | indices of integer variables with fractional value |

**What it returns**: a list of `Cut`. A `Cut(coefficients, rhs)` means `sum coefficients[j] * x[j] <= rhs`, with sparse coefficients as a dict. `Cut.from_dense(coef, rhs, "<=" | ">=")` builds one from a dense vector, and `cut.violation(x) > 0` means `x` violates it.

**Rules**
- **Cuts must be globally valid.** Every cut is valid for every integer-feasible point of the original model, because both root constraints and Gurobi user cuts apply everywhere. Derive cuts from `ctx.problem` (global bounds), not from node-local information.
- **Return violated cuts.** Validation fails cuts that the point they came from doesn't violate. Filter on `cut.violation(ctx.x) > tolerance`.
- **Keep state in `prepare`.** A fresh instance is created for every solve, and `prepare(problem, seed)` runs before the first call. Use it to cache the rows you scan and to seed an RNG.
- **Constructor arguments** can be varied without code changes through `generator_args` in a config variant.

**Where it runs**
- `root`: rounds of *solve the LP, call `separate`, add the cuts as constraints*, before Gurobi starts (`cut_options.root_rounds`).
- `node`: inside Gurobi's `MIPNODE` callback at every node with an optimal LP, cuts passed to `cbCut` (`cut_options.node_cuts_until` limits this, e.g. `0` = root node only).
- `auto` means root for tableau generators, node otherwise.

At most `cut_options.max_cuts_per_round` cuts are kept per call, so return the most violated ones first.

## Branching rules

```python
from branchcut.api import BranchingRule

class MyRule(BranchingRule):
    name = "my_rule"
    var_branch = -1           # Gurobi VarBranch: -1 auto, 0 pseudo reduced cost, 1 pseudo shadow price,
                              #                   2 max infeasibility, 3 strong
    def priorities(self, problem, seed):
        return ...            # one int per variable (higher branched first), or None
```

Gurobi has no branching callback, so rules are static: a variable selection strategy plus priorities computed from the model.

## Checks every approach must pass

`python run.py validate NAME`, or `python -m pytest tests/test_approaches.py`:
1. **Valid**: no cut removes an integer-feasible point of small instances whose feasible points are all enumerated.
2. **Separating**: each cut is violated at the point it came from.
3. **Clean**: no Gurobi cuts leaked into the log, and the generator produced cuts.
4. **Sound bound**: the root bound never passes the optimum.
5. **Correct**: the optimum matches Gurobi with its own cuts on knapsack, set-cover and facility-location instances (the last one mixed-integer).

Branching rules must produce priorities Gurobi accepts and the correct optimum.
