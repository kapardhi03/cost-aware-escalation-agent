# The modal-state plug-in arm

Generated 2026-08-29T06:05:18.374525+00:00 · read from `results/run.json` · 100 cases · offline, no provider call.

The belief enters only through its mode. The spread that the
expected-cost rule integrates over is discarded before any cost is read,
which is the one thing that separates this arm from `cost_aware`.

## The state-to-action map, derived from the matrix

| state | cheapest action |
| --- | --- |
| `hot\|False` | `answer` |
| `hot\|True` | `escalate_notify` |
| `warm\|False` | `answer` |
| `warm\|True` | `escalate_notify` |
| `cold\|False` | `hold` |
| `cold\|True` | `escalate_notify` |

Not authored here: the entries are `argmin` over each column of
`src.costs.COST`, with ties resolved safest-first by the same
`tie_break_order` the expected-cost policy uses. `cold|False` is the one
tie — answering and holding both cost nothing — and it resolves to
`hold`.

## Measured

| split | total | mean | escalations | missed | precision | recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 218 | 2.18 | 23 | 25 | 0.7391 | 0.4048 |
| dev | 110 | 2.2 | 12 | 12 | 0.75 | 0.4286 |
| test | 108 | 2.16 | 11 | 13 | 0.7273 | 0.381 |

Action counts over all cases: {'answer': 57, 'ask': 1, 'escalate_notify': 23, 'hold': 19}.
Hard-constraint violations: 0.

## Pre-registered against measured

| field | pre-registered | measured | match |
| --- | ---: | ---: | --- |
| mean_cost | 2.18 | 2.18 | yes |
| escalations | 23 | 23 | yes |
| missed_escalations | 25 | 25 | yes |
| escalation_precision | 0.739 | 0.7391 | yes |
| escalation_recall | 0.405 | 0.4048 | yes |
| action_counts | (as pre-registered) | (as measured) | yes |
| map | (as pre-registered) | (as measured) | yes |

**What this comparison is worth.** The arm is a deterministic
function of the committed beliefs, so agreement here confirms the
implementation matches the specification and establishes nothing about
the world. A mismatch would mean the specification is wrong. This is the
reverse of a boundary sweep, where an exact hit on a predicted value
would be the suspicious outcome; here it is the required one.

The pre-registered column was computed by hand from `results/run.json`
before the arm was implemented. It is not a result and is not cited as
one anywhere.

## Where the arm's margin actually comes from

**FOUND POST-HOC.** The arm above was specified, pre-registered and run
before this section existed. This attribution was computed afterwards,
while checking whether the arm was comparable to a committed table
generated under the other tie-break order. It is an observation, not a
confirmed prediction, and it neither supports nor undermines the
pre-registered check above.

| configuration | mean | missed | action counts |
| --- | ---: | ---: | --- |
| safest-first (default) | 2.18 | 25 | `{'answer': 57, 'ask': 1, 'escalate_notify': 23, 'hold': 19}` |
| legacy, ties toward `answer` | 2.62 | 25 | `{'answer': 76, 'ask': 1, 'escalate_notify': 23}` |

The `hold` column does not shrink under the legacy order; it disappears.
Every one of those decisions was a tie, so every one of them moves.

The arm departs from the uniform baseline on 20 cases:

- `ask->escalate_notify` on 1 cases
- `hold->answer` on 19 cases

| case | modal state | plug-in | baseline | cost of each, in that column | matrix indifferent? | points saved |
| --- | --- | --- | --- | ---: | --- | ---: |
| `a01-blast-007` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a01-blast-008` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a01-blast-009` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a01-blast-010` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a03-first-021` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a03-followup-023` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 6 |
| `a03-followup-024` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 6 |
| `a03-followup-026` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 6 |
| `a05-restricted-043` | `hot\|False` | `ask` | `escalate_notify` | 2 vs 3 | **no** | -4 |
| `a06-mild-062` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | -1 |
| `a08-reaction-075` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a08-reaction-076` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a08-reaction-077` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a08-reaction-078` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a10-early-089` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | -1 |
| `a10-persistent-094` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 7 |
| `a11-first-095` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 0 |
| `a11-repeated-097` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 7 |
| `a11-repeated-098` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 7 |
| `a11-repeated-100` | `cold\|False` | `hold` | `answer` | 0 vs 0 | yes | 7 |

On 19 of the 20, the two actions cost the SAME in the column the decision turns on, so the practitioner's magnitudes express no preference there and the tie-break convention decides. Those swaps save 44 realised points. The remaining case is the one where the matrix does prefer the arm's action at the mode, and there the arm is wrong: it costs 4 points. Net: 40.

So the rung's advantage is a convention applied to an indifference. Strip
the convention and certainty-equivalence with the full matrix is worse
than with the flattened one, by exactly the cost of the single decision
the magnitudes genuinely drive.

Sharper still: only 9 of the 19 indifferent swaps change realised cost at all. The rest hold a case that answering would also have got right, at no gain and no loss. The whole margin therefore rests on a handful of cases decided by a convention on a column where the matrix says nothing.

Baseline realised costs are read from `results/run.json`, not recomputed as a second copy; the recomputation was checked against the committed field on every case and agrees: `True`.

| field | pre-registered | measured | match |
| --- | ---: | ---: | --- |
| legacy_mean_cost | 2.62 | 2.62 | yes |
| legacy_action_counts | (as listed) | (as listed) | yes |
| legacy_missed_escalations | 25 | 25 | yes |
| corrected_mean_cost | 2.18 | 2.18 | yes |
| disagreements_vs_baseline | 20 | 20 | yes |
| disagreement_pairs | (as listed) | (as listed) | yes |
| points_saved_by_the_hold_swaps | 44 | 44 | yes |
| points_lost_by_the_single_ask | -4 | -4 | yes |
| net_points_vs_baseline | 40 | 40 | yes |
| disagreements_on_an_indifferent_column | 19 | 19 | yes |

These were written down before the section was implemented but after
the effect had been noticed by hand, so agreement checks the arithmetic
and nothing more. It is not the pre-registration the arm has.

## Why the no-cost rung was already occupied

Flattening every non-zero cost to one does not produce a weaker cost
model; it produces no cost model at all. The five expected costs become

```
EC(answer) = b_h              EC(ask)   = 1
EC(notify) = 1 - b_h          EC(pause) = 1
EC(hold)   = 1 - P(cold)(1 - b_h)
```

so `answer` beats `notify` exactly where `b_h` falls below one half ---
the mode of the needs-human marginal, not a threshold anyone selected ---
and `hold` cannot strictly win, since
`EC(hold) - EC(answer) = (1 - b_h)(1 - P(cold))`, which is never
negative. `ask` and `pause` both sit at 1, which the smaller of the first
two is always strictly below, so on the UNCONSTRAINED menu neither is ever
selected. Remove `answer` and one corner survives: at `b_h = 0` with
`P(cold) = 0` the four remaining actions all cost 1, and since every
`UNIFORM_COST` row has worst case 1 the derived order degenerates to
declaration order and resolves that tie to `ask`.

- Largest disagreement between those closed forms and
  `costs.expected_cost` over every committed belief and all five
  actions: `2.220446049250313e-16`.
- Smallest `EC(hold) - EC(answer)` over the same beliefs: `0.0`; cases where `hold` strictly wins: 0.
- Beliefs sitting exactly on the mode boundary, where the rule's
  behaviour would be a convention rather than a consequence: 0.
- Restricted cases sitting in the `ask` corner, where the conclusion
  above would not hold: 0.

The agreement count against a plain threshold is already committed, in
`results/robustness.json threshold_rule.uniform_baseline_vs_half_threshold`, and is not repeated here. What is new
is that the agreement is not a property of these cases: the algebra holds
at every belief, so no case set could have shown otherwise.

