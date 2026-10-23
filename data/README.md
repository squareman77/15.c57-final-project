# Benchmark data

Instances live here, grouped by source. Data files are ignored by git; commit
manifests and acquisition notes instead, and preserve each source's license.

* `generated/<family>/`: MPS files written by the generators when a config runs
  (deterministic from family, parameters and seed, so they are safe to delete)
* `miplib/`: MIPLIB 2017 instances, downloaded with
  `python run.py fetch-miplib NAME ...` or `--benchmark-list data/benchmark-v2.test`
* `benchmark-v2.test`: the MIPLIB 2017 benchmark set (committed)
* anything else, e.g. Lehigh instances: use a `files` or `manifest` scenario
