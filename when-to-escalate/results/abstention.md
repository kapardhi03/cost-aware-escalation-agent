# The cost of abstention: three variants, three arms

Beliefs: 100 cases per arm, arms `published`, `raw`, `calibrated`. Claim split: `test`; dev is in-sample and labelled.

rebaselined would add a column about cache drift, which abstention has nothing to do with (decisions/v2-gate4-preregistration.md section 5.1).

- `published` — results/run.json
- `raw` — results/logprob-elicitation.json raw + fresh readiness
- `calibrated` — results/logprob-elicitation.json calibrated + fresh readiness

## 1. What the cost matrix settles first

| readiness | needs_human | `escalate_pause` | `escalate_notify` | `answer` | pause − notify |
|---|---|---:|---:|---:|---:|
| hot | False | 6 | 3 | 0 | +3 |
| warm | False | 5 | 3 | 0 | +2 |
| cold | False | 5 | 3 | 0 | +2 |
| hot | True | 2 | 0 | 10 | +2 |
| warm | True | 1 | 0 | 10 | +1 |
| cold | True | 1 | 0 | 10 | +1 |

Any rule that turns an escalate_notify into an escalate_pause raises realised cost on every case it touches, by between 1 and 3 per case. No belief set and no tau changes that; it is arithmetic on the matrix.

is_escalation counts both escalate actions, so a notify-to-pause rewrite cannot change the miss count. Only a rule that converts a non-escalation into a pause can, and it can only lower it.

How many cases each rule touches, and whether the misses it avoids are worth the pause penalty it pays. That is what sections 3 to 6 measure.

## 2. The tau grid

Population: 100 cases of the arm being scored. Deciles, 0% to 100%.

| quantile | `published` bits | `raw` bits | `calibrated` bits |
|---|---:|---:|---:|
| 0.0 | 0.0000 | 0.0000 | 0.7219 |
| 0.1 | 1.6258 | 1.6568 | 1.1568 |
| 0.2 | 1.6258 | 1.7659 | 2.0233 |
| 0.3 | 1.8787 | 1.9293 | 2.0720 |
| 0.4 | 2.0174 | 1.9898 | 2.1260 |
| 0.5 | 2.0174 | 2.0081 | 2.2029 |
| 0.6 | 2.0174 | 2.0236 | 2.2055 |
| 0.7 | 2.0381 | 2.0487 | 2.2448 |
| 0.8 | 2.0829 | 2.1372 | 2.2953 |
| 0.9 | 2.2522 | 2.2810 | 2.3578 |
| 1.0 | 2.4564 | 2.4798 | 2.4855 |

| arm | min | median | max | distinct tau | cases at H = 0 |
|---|---:|---:|---:|---:|---:|
| `published` | 0.000000 | 2.0174 | 2.456426 | 8 | 1 |
| `raw` | 0.000001 | 2.0081 | 2.479759 | 11 | 0 |
| `calibrated` | 0.721928 | 2.2029 | 2.485475 | 11 | 0 |

The observed distribution is bunched. An absolute grid over the 0-2.585 bit theoretical range would put most of its points in a region holding almost no cases, which is the S4 failure mode this gate is checking for. Deciles make the step commensurate with the quantity by construction.

Decile values are not comparable across arms in absolute bits, because H(b) shifts when b_h shifts. Compare arms at equal quantiles, or read the bit column and accept that the same quantile is a different threshold on each arm.

A decile grid on a tied distribution repeats values. Where two quantiles give the same tau they give the same firing set and the same cost, and the rows are identical by construction rather than by coincidence.

`H(b)` is quantised to 12 decimals before any comparison against tau. Cases with the same belief can differ in the last bit of the entropy sum, and left alone that made two identical deciles read as different thresholds. What the rounding absorbs and what it preserves, per arm:

| arm | distinct H before | after | spurious removed | largest gap absorbed | smallest gap preserved | margin below signal |
|---|---:|---:|---:|---:|---:|---:|
| `published` | 24 | 19 | 5 | 8.88e-16 | 9.99e-03 | 1.0e+10x |
| `raw` | 100 | 100 | 0 | — | 3.92e-05 | 3.9e+07x |
| `calibrated` | 88 | 88 | 0 | — | 4.97e-06 | 5.0e+06x |

The tolerance is 1e-12 bits. It has to sit above the float noise bound (3.55e-15, eight ulp at the largest `H(b)`) so it absorbs last-bit differences, and below the smallest genuine gap so it merges nothing real. Both ends are checked per arm, and gaps are classified by the noise bound rather than by the tolerance so the test is not circular.

The published arm's recomputed `H(b)` agrees with results/answer-model.json per_case.cases[].h_joint on all 100 cases, max absolute delta 0. The committed column is on published beliefs only, which is why the other two arms recompute rather than read it.

## 3. The baseline, which is what (c) leaves in place

Test split. Checked against `results/rebaseline.json` rather than trusted because it shares definitions with it.

| arm | total cost | mean cost | misses | action counts | reproduces committed |
|---|---:|---:|---:|---|---|
| `published` | 86 | 1.72 | 8 | `{'answer': 15, 'escalate_notify': 20, 'hold': 15}` | True |
| `raw` | 70 | 1.4 | 7 | `{'answer': 12, 'escalate_notify': 21, 'hold': 17}` | True |
| `calibrated` | 75 | 1.5 | 2 | `{'escalate_notify': 41, 'hold': 9}` | True |

Dev split, in-sample:

| arm | total cost | mean cost | misses | action counts |
|---|---:|---:|---:|---|
| `published` | 79 | 1.58 | 8 | `{'answer': 14, 'escalate_notify': 23, 'hold': 13}` |
| `raw` | 76 | 1.52 | 7 | `{'answer': 13, 'escalate_notify': 24, 'hold': 13}` |
| `calibrated` | 83 | 1.66 | 3 | `{'escalate_notify': 42, 'hold': 8}` |

| arm | tie-break changes actions on test | on dev | cases |
|---|---|---|---|
| `published` | False | True | `a11-repeated-097` answer to hold |
| `raw` | False | False | — |
| `calibrated` | False | False | — |

The committed scores this artifact checks itself against are test-split scores. Where the two rules differ on dev, the dev columns here report the fresh rule and run.json reports the legacy one.

## 4. Variant (b): the fallback rewrite

`VoI <= 0` holds on every case on every arm, so "`ask` lost only because `VoI <= 0`" is true everywhere and (b) is not a tie-break. Its scope is cases whose myopic action was escalate_notify. It is tau-independent.

| arm | cases rewritten | fraction | total cost | delta | mean cost | misses | delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| `published` | 20 | 0.40 | 118 | +32 | 2.36 | 8 | 0 |
| `raw` | 21 | 0.42 | 103 | +33 | 2.06 | 7 | 0 |
| `calibrated` | 41 | 0.82 | 149 | +74 | 2.98 | 2 | 0 |

The miss delta is zero on every arm, and it has to be: both actions count as escalations, so no notify-to-pause rewrite can change a miss. (b) buys nothing measurable on the miss axis and pays the pause penalty on every case it touches.

## 5. Variant (a): the H(b) threshold override

`H(b) >= tau` forces `escalate_pause`. `escalate_pause` is feasible on every case, so no firing is ever skipped.

The grid is taken over all 100 cases and the scoring is on the 50 test cases. If an arm's highest-entropy case is a dev case, tau at the 100th percentile is above every test case and the firing set is empty. That is the population choice showing through, not a failed comparison.

### `published` — baseline 86 cost, 8 misses

| quantile | tau bits | firing | changed | total cost | delta | misses | delta | cost per miss avoided |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.0000 | 50 | 50 | 177 | +91 | 0 | -8 | 11.38 |
| 0.1 | 1.6258 | 49 | 49 | 172 | +86 | 0 | -8 | 10.75 |
| 0.2 | 1.6258 | 49 | 49 | 172 | +86 | 0 | -8 | 10.75 |
| 0.3 | 1.8787 | 36 | 36 | 172 | +86 | 3 | -5 | 17.2 |
| 0.4 | 2.0174 | 32 | 32 | 152 | +66 | 3 | -5 | 13.2 |
| 0.5 | 2.0174 | 32 | 32 | 152 | +66 | 3 | -5 | 13.2 |
| 0.6 | 2.0174 | 32 | 32 | 152 | +66 | 3 | -5 | 13.2 |
| 0.7 | 2.0381 | 14 | 14 | 101 | +15 | 6 | -2 | 7.5 |
| 0.8 | 2.0829 | 11 | 11 | 104 | +18 | 8 | 0 | — |
| 0.9 | 2.2522 | 9 | 9 | 102 | +16 | 8 | 0 | — |
| 1.0 | 2.4564 | 1 | 1 | 88 | +2 | 8 | 0 | — |

Beats baseline at any tau on this split: False. Cheapest grid point: quantile 1.0 (2.4564 bits), cost 88, +2 against baseline. Reported because the grid was pre-registered before any of these numbers existed. It is not a selected tau: no value here was chosen to make a variant look good, and picking the argmin on the split being scored would be selection on the test half.

### `raw` — baseline 70 cost, 7 misses

| quantile | tau bits | firing | changed | total cost | delta | misses | delta | cost per miss avoided |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.0000 | 50 | 50 | 177 | +107 | 0 | -7 | 15.29 |
| 0.1 | 1.6568 | 47 | 47 | 170 | +100 | 0 | -7 | 14.29 |
| 0.2 | 1.7659 | 40 | 40 | 156 | +86 | 1 | -6 | 14.33 |
| 0.3 | 1.9293 | 36 | 36 | 153 | +83 | 2 | -5 | 16.6 |
| 0.4 | 1.9898 | 31 | 31 | 134 | +64 | 3 | -4 | 16.0 |
| 0.5 | 2.0081 | 25 | 25 | 119 | +49 | 5 | -2 | 24.5 |
| 0.6 | 2.0236 | 19 | 19 | 116 | +46 | 7 | 0 | — |
| 0.7 | 2.0487 | 16 | 16 | 104 | +34 | 7 | 0 | — |
| 0.8 | 2.1372 | 12 | 12 | 92 | +22 | 7 | 0 | — |
| 0.9 | 2.2810 | 5 | 5 | 79 | +9 | 7 | 0 | — |
| 1.0 | 2.4798 | 0 | 0 | 70 | 0 | 7 | 0 | — |

Beats baseline at any tau on this split: False. Cheapest grid point: quantile 1.0 (2.4798 bits), cost 70, 0 against baseline. Reported because the grid was pre-registered before any of these numbers existed. It is not a selected tau: no value here was chosen to make a variant look good, and picking the argmin on the split being scored would be selection on the test half.

### `calibrated` — baseline 75 cost, 2 misses

| quantile | tau bits | firing | changed | total cost | delta | misses | delta | cost per miss avoided |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.7219 | 50 | 50 | 177 | +102 | 0 | -2 | 51.0 |
| 0.1 | 1.1568 | 50 | 50 | 177 | +102 | 0 | -2 | 51.0 |
| 0.2 | 2.0233 | 42 | 42 | 162 | +87 | 0 | -2 | 43.5 |
| 0.3 | 2.0720 | 35 | 35 | 147 | +72 | 1 | -1 | 72.0 |
| 0.4 | 2.1260 | 31 | 31 | 141 | +66 | 1 | -1 | 66.0 |
| 0.5 | 2.2029 | 26 | 26 | 131 | +56 | 2 | 0 | — |
| 0.6 | 2.2055 | 19 | 19 | 112 | +37 | 2 | 0 | — |
| 0.7 | 2.2448 | 16 | 16 | 103 | +28 | 2 | 0 | — |
| 0.8 | 2.2953 | 10 | 10 | 92 | +17 | 2 | 0 | — |
| 0.9 | 2.3578 | 5 | 5 | 84 | +9 | 2 | 0 | — |
| 1.0 | 2.4855 | 1 | 1 | 77 | +2 | 2 | 0 | — |

Beats baseline at any tau on this split: False. Cheapest grid point: quantile 1.0 (2.4855 bits), cost 77, +2 against baseline. Reported because the grid was pre-registered before any of these numbers existed. It is not a selected tau: no value here was chosen to make a variant look good, and picking the argmin on the split being scored would be selection on the test half.

## 6. Variant (c): the flag, and what it would have cost to act

Cost is the baseline cost at every tau, by construction. What varies is how many cases carry the flag and how many of those the baseline already escalates.

### `published`

| quantile | tau bits | flagged | of those, need a human | of those, already escalated |
|---|---:|---:|---:|---:|
| 0.0 | 0.0000 | 50 | 21 | 20 |
| 0.1 | 1.6258 | 49 | 21 | 20 |
| 0.2 | 1.6258 | 49 | 21 | 20 |
| 0.3 | 1.8787 | 36 | 11 | 13 |
| 0.4 | 2.0174 | 32 | 11 | 13 |
| 0.5 | 2.0174 | 32 | 11 | 13 |
| 0.6 | 2.0174 | 32 | 11 | 13 |
| 0.7 | 2.0381 | 14 | 8 | 12 |
| 0.8 | 2.0829 | 11 | 5 | 11 |
| 0.9 | 2.2522 | 9 | 3 | 9 |
| 1.0 | 2.4564 | 1 | 0 | 1 |

### `raw`

| quantile | tau bits | flagged | of those, need a human | of those, already escalated |
|---|---:|---:|---:|---:|
| 0.0 | 0.0000 | 50 | 21 | 21 |
| 0.1 | 1.6568 | 47 | 19 | 19 |
| 0.2 | 1.7659 | 40 | 14 | 15 |
| 0.3 | 1.9293 | 36 | 12 | 14 |
| 0.4 | 1.9898 | 31 | 11 | 14 |
| 0.5 | 2.0081 | 25 | 9 | 14 |
| 0.6 | 2.0236 | 19 | 7 | 14 |
| 0.7 | 2.0487 | 16 | 6 | 13 |
| 0.8 | 2.1372 | 12 | 5 | 11 |
| 0.9 | 2.2810 | 5 | 1 | 5 |
| 1.0 | 2.4798 | 0 | 0 | 0 |

### `calibrated`

| quantile | tau bits | flagged | of those, need a human | of those, already escalated |
|---|---:|---:|---:|---:|
| 0.0 | 0.7219 | 50 | 21 | 41 |
| 0.1 | 1.1568 | 50 | 21 | 41 |
| 0.2 | 2.0233 | 42 | 14 | 34 |
| 0.3 | 2.0720 | 35 | 12 | 30 |
| 0.4 | 2.1260 | 31 | 9 | 26 |
| 0.5 | 2.2029 | 26 | 8 | 23 |
| 0.6 | 2.2055 | 19 | 6 | 18 |
| 0.7 | 2.2448 | 16 | 6 | 16 |
| 0.8 | 2.2953 | 10 | 3 | 10 |
| 0.9 | 2.3578 | 5 | 1 | 5 |
| 1.0 | 2.4855 | 1 | 0 | 1 |

## 7. Resolving a firing case: pause against notify against answer

Test split, H(b) descending, so any tau's firing set is a prefix. The `answer` column is the cost of resolving an uncertain case by answering anyway, which is the alternative abstention exists to avoid. Cases carrying no_direct_answer cannot answer at all, so the three-way comparison is taken on the answer-feasible subset of each firing set and the excluded count is reported next to it. 4 of the 50 test cases carry it.

### `published`

Whole firing set:

| quantile | firing | all pause | all notify | baseline on the firing set |
|---|---:|---:|---:|---:|
| 0.0 | 50 | 177 | 87 | 86 |
| 0.1 | 49 | 172 | 84 | 86 |
| 0.2 | 49 | 172 | 84 | 86 |
| 0.3 | 36 | 142 | 75 | 56 |
| 0.4 | 32 | 122 | 63 | 56 |
| 0.5 | 32 | 122 | 63 | 56 |
| 0.6 | 32 | 122 | 63 | 56 |
| 0.7 | 14 | 40 | 18 | 25 |
| 0.8 | 11 | 36 | 18 | 18 |
| 0.9 | 9 | 34 | 18 | 18 |
| 1.0 | 1 | 5 | 3 | 3 |

Three-way, on the answer-feasible subset of each firing set:

| quantile | answer-feasible | excluded | `escalate_pause` | `escalate_notify` | `answer` |
|---|---:|---:|---:|---:|---:|
| 0.0 | 46 | 4 | 170 | 87 | 170 |
| 0.1 | 45 | 4 | 165 | 84 | 170 |
| 0.2 | 45 | 4 | 165 | 84 | 170 |
| 0.3 | 35 | 1 | 140 | 75 | 100 |
| 0.4 | 31 | 1 | 120 | 63 | 100 |
| 0.5 | 31 | 1 | 120 | 63 | 100 |
| 0.6 | 31 | 1 | 120 | 63 | 100 |
| 0.7 | 13 | 1 | 38 | 18 | 70 |
| 0.8 | 10 | 1 | 34 | 18 | 40 |
| 0.9 | 8 | 1 | 32 | 18 | 20 |
| 1.0 | 1 | 0 | 5 | 3 | 0 |

### `raw`

Whole firing set:

| quantile | firing | all pause | all notify | baseline on the firing set |
|---|---:|---:|---:|---:|
| 0.0 | 50 | 177 | 87 | 70 |
| 0.1 | 47 | 170 | 84 | 70 |
| 0.2 | 40 | 152 | 78 | 66 |
| 0.3 | 36 | 139 | 72 | 56 |
| 0.4 | 31 | 116 | 60 | 52 |
| 0.5 | 25 | 93 | 48 | 44 |
| 0.6 | 19 | 69 | 36 | 23 |
| 0.7 | 16 | 57 | 30 | 23 |
| 0.8 | 12 | 41 | 21 | 19 |
| 0.9 | 5 | 21 | 12 | 12 |
| 1.0 | 0 | 0 | 0 | 0 |

Three-way, on the answer-feasible subset of each firing set:

| quantile | answer-feasible | excluded | `escalate_pause` | `escalate_notify` | `answer` |
|---|---:|---:|---:|---:|---:|
| 0.0 | 46 | 4 | 170 | 87 | 170 |
| 0.1 | 44 | 3 | 164 | 84 | 160 |
| 0.2 | 39 | 1 | 150 | 78 | 130 |
| 0.3 | 35 | 1 | 137 | 72 | 110 |
| 0.4 | 30 | 1 | 114 | 60 | 100 |
| 0.5 | 24 | 1 | 91 | 48 | 80 |
| 0.6 | 18 | 1 | 67 | 36 | 60 |
| 0.7 | 15 | 1 | 55 | 30 | 50 |
| 0.8 | 11 | 1 | 39 | 21 | 40 |
| 0.9 | 5 | 0 | 21 | 12 | 10 |
| 1.0 | 0 | 0 | 0 | 0 | 0 |

### `calibrated`

Whole firing set:

| quantile | firing | all pause | all notify | baseline on the firing set |
|---|---:|---:|---:|---:|
| 0.0 | 50 | 177 | 87 | 75 |
| 0.1 | 50 | 177 | 87 | 75 |
| 0.2 | 42 | 162 | 84 | 75 |
| 0.3 | 35 | 134 | 69 | 62 |
| 0.4 | 31 | 125 | 66 | 59 |
| 0.5 | 26 | 102 | 54 | 46 |
| 0.6 | 19 | 73 | 39 | 36 |
| 0.7 | 16 | 58 | 30 | 30 |
| 0.8 | 10 | 38 | 21 | 21 |
| 0.9 | 5 | 21 | 12 | 12 |
| 1.0 | 1 | 5 | 3 | 3 |

Three-way, on the answer-feasible subset of each firing set:

| quantile | answer-feasible | excluded | `escalate_pause` | `escalate_notify` | `answer` |
|---|---:|---:|---:|---:|---:|
| 0.0 | 46 | 4 | 170 | 87 | 170 |
| 0.1 | 46 | 4 | 170 | 87 | 170 |
| 0.2 | 41 | 1 | 160 | 84 | 130 |
| 0.3 | 34 | 1 | 132 | 69 | 110 |
| 0.4 | 30 | 1 | 123 | 66 | 80 |
| 0.5 | 25 | 1 | 100 | 54 | 70 |
| 0.6 | 18 | 1 | 71 | 39 | 50 |
| 0.7 | 15 | 1 | 56 | 30 | 50 |
| 0.8 | 10 | 0 | 38 | 21 | 30 |
| 0.9 | 5 | 0 | 21 | 12 | 10 |
| 1.0 | 1 | 0 | 5 | 3 | 0 |

## 8. The call

Status: open at the time this artifact was written. Made by Kaps, at the Gate 4 close, on these numbers.

tau was defined as deciles before any of these costs existed, and no variant was tuned. If (a) or (b) beats (c) on realised cost that is reported plainly here, whatever it does to the no-free-parameters claim.

It does not recommend a variant. The measurement and the recommendation are kept separate so they cannot be read as one thing.
