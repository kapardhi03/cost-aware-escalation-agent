# The results table, with the three columns it was missing

Read from `results/run.json`; that file is unchanged and remains the source for every column that was already there. Accuracy, the information/decision split and the human-routing rate are computed here.

| policy | accuracy | precision | recall | missed | decision cost | info cost | human % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cost_aware` | 0.67 | 0.6047 | 0.619 | 16 | 1.72 | 0.0 | 43.0 |
| `uniform_baseline` | 0.7 | 0.75 | 0.4286 | 24 | 2.58 | 0.0 | 24.0 |
| `always_notify` | 0.42 | 0.42 | 1.0 | 0 | 1.74 | 0.0 | 100.0 |
| `always_ask` | 0.58 | -- | 0.0 | 42 | 0.0 | 2.84 | 0.0 |
| `always_answer` | 0.66 | 1.0 | 0.1905 | 34 | 3.4 | 0.0 | 8.0 |

## Two entries of the accuracy column are forced

The label base rate is **0.42**. `always_notify` escalates everywhere, so its accuracy is its precision and both are the base rate (True, True). `always_ask` escalates nowhere, so its accuracy is one minus the base rate — the majority-class score, which the table therefore already contains (True).

## `human %` replaces the old escalation count, it does not join it

| policy | committed escalations | recomputed | human % | equal |
| --- | ---: | ---: | ---: | :---: |
| `cost_aware` | 43 | 43 | 43.0 | True |
| `uniform_baseline` | 24 | 24 | 24.0 | True |
| `always_notify` | 100 | 100 | 100.0 | True |
| `always_ask` | 0 | 0 | 0.0 | True |
| `always_answer` | 8 | 8 | 8.0 | True |

## The cost-aware row under the corrected tie-break

Decisions that change: **1** (a11-repeated-097). Columns that move: **mean_decision_cost**. Only the decision cost moves: **True**, so the footnote's claim survives the three new columns.

legacy 1.72 → corrected 1.65

## Old columns, recomputed against the committed run

| policy | mean_cost | precision | recall | missed_escalations |
| --- | :---: | :---: | :---: | :---: |
| `cost_aware` | True | True | True | True |
| `uniform_baseline` | True | True | True | True |
| `always_notify` | True | True | True | True |
| `always_ask` | True | True | True | True |
| `always_answer` | True | True | True | True |

## Pre-registration

_arithmetic check, not a prediction — the values were computed by hand from the committed rows first._

All fields match: **True**
