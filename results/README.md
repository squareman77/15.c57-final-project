# Results

Benchmark outputs, ignored by git. Each run of `python run.py bench CONFIG` writes
`results/<config name>/<timestamp>/`:

* `config.toml`: the exact config used
* `environment.json`: solver and Python versions, platform, git commit (and
  whether the tree was dirty), SHA-256 of every approach file used
* `runs.jsonl`: one row per (instance, strategy, branching, seed), appended and
  flushed as each solve finishes; `--resume <dir>` continues an interrupted run
* `summary.md`: overview, per-family and per-instance tables (rebuild with
  `python run.py report <dir>`)
* `runs.csv`: the same rows, flattened for spreadsheets
* `logs/`: Gurobi logs, when the config sets `keep_logs = true`

Row fields include `status`, `objective`, `best_bound`, `gap`, `root_bound`,
`lp_bound`, `runtime`, `work`, `nodes`, `simplex_iterations`, `cuts_added`,
`root_cuts_added`, `user_cuts_applied`, `cuts_generated`, `separation_seconds`,
`backend_cuts`, `root_bound_history`, `parameters` and `message` (errors).
