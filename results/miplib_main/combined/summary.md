# miplib_main

Baseline cut families on 30 MIPLIB 2017 instances: 10 easy, 10 borderline, 10 unsolvable in 600 s.

* results: `results/miplib_main/combined`
* runs: 450 on 30 instances, seeds [0, 1, 2], time limit 600 s
* baseline: `none`, reference: `backend`
* solver: gurobi 13.0.3, commit 354ab182c6

## Overview

| strategy | runs | optimal | time limit | errors | wrong | sgm time (s) | time vs baseline | sgm nodes | nodes vs baseline | sgm work | root gap closed (%) | cuts added | sep share (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| backend | 90 | 63 | 27 | 0 | 0 | 106 | 0.641 | 32,203 | 0.214 | 140 | 35.5 | 0 | 0 |
| none | 90 | 53 | 37 | 0 | 0 | 166 | 1 | 150,300 | 1 | 220 | 0.858 | 0 | 0 |
| gmi | 90 | 39 | 51 | 0 | 0 | 304 | 1.84 | 56,361 | 0.375 | 505 | 12.6 | 388 | 2.03 |
| cover | 90 | 40 | 50 | 0 | 0 | 272 | 1.64 | 78,874 | 0.525 | 129 | 1.11 | 256 | 40.2 |
| gmi+cover | 90 | 30 | 60 | 0 | 0 | 379 | 2.29 | 42,238 | 0.281 | 405 | 12.6 | 632 | 24.7 |

## By family: sgm time (s)

| strategy | borderline | easy | unsolvable |
|---|---|---|---|
| backend | 101 | 20.6 | 559 |
| none | 298 | 24.7 | 600 |
| gmi | 421 | 111 | 600 |
| cover | 451 | 74.1 | 600 |
| gmi+cover | 558 | 163 | 600 |

## By family: mean root gap closed (%)

| strategy | borderline | easy | unsolvable |
|---|---|---|---|
| backend | 36 | 16.7 | 54 |
| none | 0.297 | 0 | 2.28 |
| gmi | 11.6 | 8.73 | 17.6 |
| cover | 1.07 | 0 | 2.28 |
| gmi+cover | 11.6 | 8.73 | 17.6 |

## Per instance: sgm time (s) over seeds

Flags: TL = time limit hit, ERR = error, WRONG = disagrees with the proven optimum.

| instance | best known | backend | none | gmi | cover | gmi+cover |
|---|---|---|---|---|---|---|
| binkar10_1 | 6,742 | 5.17 | 318.34 | 600.01 TL | 309.01 | 600.01 TL |
| bnatt400 | 1 | 142.12 | 261.00 | 272.85 | 600.03 TL | 600.05 TL |
| csched007 | 351 | 210.96 | 600.00 TL | 600.02 TL | 600.00 TL | 600.02 TL |
| gen-ip002 | -4,784 | 396.11 | 358.38 | 600.00 TL | 403.70 | 600.00 TL |
| icir97_tension | 6,375 | 147.27 | 137.85 | 252.64 | 211.05 | 317.26 TL |
| mas74 | 11,801 | 184.58 | 178.02 | 600.00 TL | 310.37 | 600.00 TL |
| neos5 | 15 | 74.71 | 411.44 | 600.00 TL | 600.01 TL | 600.00 TL |
| rocI-4-11 | -6,020,203 | 157.47 | 88.54 | 90.97 | 546.87 TL | 551.07 TL |
| rococoC10-001000 | 11,460 | 96.60 | 580.30 TL | 600.02 TL | 600.00 TL | 600.03 TL |
| timtab1 | 764,772 | 49.82 | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL |
| air05 | 26,374 | 5.43 | 13.76 | 135.54 | 51.87 | 187.49 |
| eil33-2 | 934 | 7.30 | 6.53 | 176.89 | 117.98 | 287.98 |
| glass4 | 1,200,012,600 | 121.83 | 56.68 | 82.43 | 234.11 | 213.43 |
| graphdraw-domain | 19,686 | 155.10 | 101.04 | 249.86 | 600.00 TL | 600.00 TL |
| neos-5107597-kakapo | 3,645 | 43.68 | 51.51 | 50.89 | 60.22 | 57.03 |
| ns1208400 | 2 | 3.75 | 23.83 | 151.42 | 69.89 | 295.12 |
| pk1 | 11 | 21.97 | 22.18 | 67.17 | 25.85 | 70.83 |
| qap10 | 340 | 17.44 | 11.10 | 222.15 | 11.63 | 229.29 |
| rmatr100-p10 | 423 | 12.31 | 17.92 | 18.03 | 20.75 | 20.46 |
| sct2 | -231 | 16.95 | 26.96 | 259.78 | 199.55 | 319.19 |
| 50v-10 | 3,312 | 600.00 TL | 600.00 TL | 600.01 TL | 600.00 TL | 600.01 TL |
| assign1-5-8 | 212 | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL |
| cost266-UUE | 25,162,226 | 600.00 TL | 600.00 TL | 600.01 TL | 600.00 TL | 600.04 TL |
| ic97_potential | 3,942 | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL |
| lotsize | 1,480,195 | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL |
| neos-3627168-kasai | 988,586 | 355.13 TL | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL |
| neos-4954672-berkel | 2,612,710 | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL | 600.00 TL |
| ran14x18-disj-8 | 3,712 | 502.47 TL | 600.00 TL | 600.00 TL | 600.01 TL | 600.01 TL |
| reblock115 | -36,800,603 | 600.00 TL | 600.00 TL | 600.01 TL | 600.02 TL | 600.03 TL |
| seymour | 423 | 600.00 TL | 600.00 TL | 600.01 TL | 600.02 TL | 600.08 TL |

## Problems

none

## Definitions

* **sgm**: shifted geometric mean, with a shift of 1 s for time, 10 for nodes and 1 for Gurobi work units.
  Time is wall clock, including root cut rounds and Python separation; work is Gurobi's deterministic measure of solver effort only.
* **vs baseline**: ratio of sgm values over the instance × seed runs that both strategies completed, under the same branching rule. Below 1 means faster or smaller than the baseline.
* **time vs `<rule>`** (only with several branching rules): the same ratio, against the same cut strategy under the first branching rule in the config.
* **root gap closed**: (LP bound − root bound) / (LP bound − best known). The root bound is the root LP objective after the last round of cuts (Gurobi's, ours, or both), before branching; it measures cut strength alone, without root strong branching or integer rounding of the bound.
* **wrong**: the solver reported optimal but the objective differs from the reference, or a dual bound passed the proven optimum. A non-zero count means an invalid cut.
* **sep share**: share of the run's time spent inside cut generators.
