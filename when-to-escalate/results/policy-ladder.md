# The modal-state plug-in arm

Generated 2026-08-29T05:18:45.686632+00:00 · read from `results/run.json` · 100 cases · offline, no provider call.

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
negative. `ask` and `pause` sit at 1 and are unreachable.

- Largest disagreement between those closed forms and
  `costs.expected_cost` over every committed belief and all five
  actions: `2.220446049250313e-16`.
- Smallest `EC(hold) - EC(answer)` over the same beliefs: `0.0`; cases where `hold` strictly wins: 0.
- Beliefs sitting exactly on the mode boundary, where the rule's
  behaviour would be a convention rather than a consequence: 0.

The agreement count against a plain threshold is already committed, in
`results/robustness.json threshold_rule.uniform_baseline_vs_half_threshold`, and is not repeated here. What is new
is that the agreement is not a property of these cases: the algebra holds
at every belief, so no case set could have shown otherwise.

