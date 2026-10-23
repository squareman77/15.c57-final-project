# Experiment configs

One TOML file per experiment. Run it with `python run.py bench configs/<file>.toml`; add `--dry-run` to see the matrix first. Unknown keys are errors, so typos fail before anything is solved.

## Keys

| key | default | meaning |
|---|---|---|
| `name` | required | results go to `results/<name>/<timestamp>/` |
| `description` | `""` | shown at the top of `summary.md` |
| `strategies` | required | cut strategy labels: `backend`, `none`, generator names, `a+b`, `backend+a`, or variant labels |
| `branching` | `["default"]` | branching rules: Gurobi built-ins or approach names |
| `seeds` | `[0]` | Gurobi `Seed`; each seed is a separate run |
| `time_limit` | `60` | seconds per run, including root cut rounds; `0` = none |
| `baseline` | `"none"` | strategy used for the "vs baseline" ratios; `""` disables them |
| `reference` | `"backend"` | strategy whose optimum is trusted for the "wrong" check; `""` uses the consensus |
| `validate` | `true` | validate the approaches used before benchmarking |
| `keep_logs` | `false` | keep every Gurobi log under `logs/` |
| `[solver]` | `{}` | Gurobi parameters for every run (e.g. `Threads = 1`, `MIPGap = 0`) |
| `[cut_options]` | see below | defaults for every strategy |
| `[variants.<label>]` | | named strategies: `cuts` (required), `cut_options`, `solver`, `generator_args = { gen = { arg = value } }` |
| `[[scenarios]]` | required | instance sources, see below |

`cut_options`:

| option | default | meaning |
|---|---|---|
| `root_rounds` | `10` | manual LP rounds for root-placed generators |
| `max_cuts_per_round` | `50` | cuts kept per generator call |
| `placement` | per generator | override every generator: `root`, `node`, `both` |
| `node_cuts_until` | none | separate in the callback only while the node count is at most this (`0` = root node only) |
| `max_tableau_size` | `2e7` | skip the dense tableau when rows × columns is larger |

## Scenarios

```toml
[[scenarios]]                       # generated: knapsack | set_cover | facility_location
family = "knapsack"
count = 5                           # seeds seed .. seed+count-1
seed = 100
params = { n = 60, m = 8 }          # generator arguments (see src/branchcut/scenarios/generators.py)

[[scenarios]]
family = "miplib"                   # fetch first: python run.py fetch-miplib NAME ...
names = ["pk1", "gen-ip054"]        # and/or list = "data/benchmark-v2.test", limit = 20

[[scenarios]]
family = "files"                    # any .mps / .mps.gz / .lp files
paths = ["data/lehigh/*.mps.gz"]
label = "lehigh"                    # family name in reports

[[scenarios]]
family = "manifest"                 # JSON array of {name, family, source, path[, metadata]}
path = "data/my_manifest.json"
```

Generator parameters: `knapsack(n, m, tightness)`, `set_cover(rows, cols, density, max_cost)`, `facility_location(facilities, customers, capacity_ratio, strong_linking)`.

## Included configs

| config | purpose |
|---|---|
| `smoke.toml` | about 20 s; every baseline, both example approaches, a variant, two branching rules |
| `families.toml` | 15 instances × 8 strategies × 3 seeds across the three generated families (roughly an hour) |
| `miplib.toml` | small MIPLIB 2017 benchmark instances (download them first) |
