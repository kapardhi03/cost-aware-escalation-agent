# Re-baseline — separating belief drift from the calibration map

Generated 2026-08-24T21:59:42.247543+00:00 · split `test` · n = 50 · no API calls

The temperature-0 reproduction check found **11 of 100** written `needs_human` values differ from v1's cached beliefs (89% match). The beliefs v1's published numbers were computed on cannot be reproduced today, so a direct comparison against those numbers would mix the calibration map with whatever changed between the cache dates. Each contrast below varies one thing.

## The three arms

| arm | beliefs | `needs_human` from | mean cost | missed esc. | escalates |
| --- | --- | --- | ---: | ---: | ---: |
| published (v1, committed) | v1 cache | written digit | 1.7200 | 8 | 20/50 |
| re-baselined | **fresh** | written digit | 1.7200 | 8 | 20/50 |
| raw continuous | **fresh** | logprob expectation | 1.4000 | 7 | 21/50 |
| calibrated | **fresh** | isotonic(raw) | 1.5000 | 2 | 41/50 |
| _always_notify (reference)_ | _none_ | _ignores the belief_ | _1.7400_ | _0_ | _50/50_ |

The last row is a trivial policy that escalates unconditionally. It never reads a belief, so its realised cost is a function of the labels alone and no amount of belief drift can move it — the one number here that compares across cache dates with no caveat. It is included because an arm that escalates most of the split has to be measured against escalating all of it.

## What each contrast isolates

**Belief drift across cache dates** — published vs re-baselined, both the written digit, the belief source the only difference: mean cost 1.7200 → 1.7200 (+0.0000), missed escalations 8 → 8 (+0).

**That aggregate zero is a coincidence, not stability.** On the claim split 6 written values moved and 3 of them crossed a decision boundary; the realised-cost deltas of those 3 sum to exactly 0, and the action counts cancel term for term. The miss count is unchanged at 8 but `identical_cases: false` — drift fixed `a10-persistent-091` and introduced `a02-deep-017`. Read the aggregate as "drift did not happen to move the totals here", never as "the beliefs are stable".

| case | `needs_human` v1 → fresh | action v1 → fresh | cost v1 → fresh |
| --- | ---: | --- | ---: |
| `a02-deep-017` | 0.3 → 0.2 | escalate_notify → answer | 0 → 10 |
| `a04-booking-035` | 0.1 → 0.2 | answer → answer _(no action change)_ | 10 → 10 |
| `a04-booking-040` | 0.9 → 0.3 | escalate_notify → escalate_notify _(no action change)_ | 0 → 0 |
| `a07-internals-068` | 0.4 → 0.7 | escalate_notify → escalate_notify _(no action change)_ | 0 → 0 |
| `a10-persistent-091` | 0.2 → 0.4 | hold → escalate_notify | 3 → 0 |
| `a11-repeated-100` | 0.1 → 0.2 | answer → hold | 10 → 3 |

**The calibration map** — raw vs calibrated, same fresh beliefs, same fresh readiness, the map the only difference: mean cost 1.4000 → 1.5000 (+0.1000), missed escalations 7 → 2 (-5).

**The two secondary metrics move in opposite directions.** Calibration cuts misses from 7 to 2 and raises mean cost by +0.1000. The mechanism is visible in the action counts: the map lifts the low scores enough that the myopic rule escalates 41 of 50 cases instead of 21, so escalation recall rises (0.6667 → 0.9048) while precision falls (0.6667 → 0.4634). Better-calibrated probabilities move the operating point along the cost/miss trade-off; they do not dominate the uncalibrated arm on both metrics at once. That is a finding about the fixed cost matrix and the one-step rule, not a defect in the map, and it is why the Gate 2 claim is the calibration metrics rather than the cost proxy.

The second contrast is the calibration-only before/after. The first is reported so the drift is visible and is never attributed to the map.

## These are the secondary metrics

> The test split carries only 8 of v1's 16 escalation misses, so a change of one or two misses is not evidence. Mean cost and miss count are reported alongside the calibration metrics and are not the claim.

The Gate 2 claim is the held-out calibration result, not these numbers:

| metric | raw | calibrated |
| --- | ---: | ---: |
| cross-entropy (bits) | 0.8546 | 0.8136 |
| ECE | 0.1526 | 0.0696 |
| Brier | 0.2063 | 0.1962 |

## Limitations, recorded

- **Temperature-0 reproduction is 89%, not 100%.** 11 of 100 cases wrote a different value than v1 cached, at temperature 0 with a byte-identical prompt. The cause is not determinable from the record: both runs asked for the alias `gpt-4o-mini`, but v1 stored the alias it requested while v2 stores the snapshot the API resolved to, so a snapshot change between the two cache dates and serving-side nondeterminism at temperature 0 are equally consistent with the evidence. `temperature=0` pins the sampler, not the weights. Recorded as limitation L10; the fix applied from v2 on is to store the resolved model id. Every cross-date comparison in this project inherits the limit.
- **The test split carries only 8 of v1's 16 missed escalations**, so a change of one or two misses is inside noise and is not evidence. The calibration contrast moves 5, which is past that floor — but it arrives with a mean-cost increase and a precision drop, so it is a shift in operating point, not a free improvement.
- **The aggregate drift contrast is zero by coincidence.** 3 actions changed and their costs cancelled. The per-case table above is the honest version; the aggregate row is not evidence that the beliefs are stable.
- **Ordering is not preserved on test** (`order_preserved_on_test: false`). The isotonic map merges distinct scores by construction. Carried forward as an open flag for the value-of-information ceiling, which reads the ordering.
- **Tie-break rule does not move these numbers** (`identical: true`): both the legacy and fixed tie-break give the same mean cost and miss count on every arm, so the drift contrast is not an artefact of that choice.

