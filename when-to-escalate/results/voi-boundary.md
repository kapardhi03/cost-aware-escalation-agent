# Where a policy that may ask actually starts asking

Beliefs, constraints and labels from `results/run.json`, unmodified. The analytic boundary is read from `results/voi-ceiling.json`, not retyped. Every quantity below is exact rational arithmetic.

## The real menu

At the practitioner's prices ($\lambda = 1$) P3 asks on **0** of 100 cases, and the oracle version -- which credits a question with the entire cost of acting -- asks on **0**. P3 therefore plays P2's action on all 100 cases under the corrected tie-break, and on 99 of the decisions as committed in `run.json`, which was generated under the legacy order and differs on 1 case (`a11-repeated-097`) for that reason and no other (True). This is the result, not the absence of one: the lookahead is built, it is priced against the committed matrix, and it declines to buy.

## The switch

| | lambda | as decimal |
| --- | ---: | ---: |
| analytic boundary (committed) | $15/16$ | 0.937500 |
| oracle switch, measured | $5/6$ | 0.833333 |
| real switch, measured | $11/30$ | 0.366667 |

Attained by `a01-first-003` and, for the real arm, by `a01-first-003` with `q_authority`.

## The offset, and its cause

The oracle switch sits **5/48** (0.104167) below the analytic boundary. Cause: **belief quantization**.

The boundary is attained at $b_h = 3/13$ with all readiness mass on hot. Pushing that belief through this script's own expected-cost code gives $15/16$, which reproduces the committed boundary (True) -- so the algebra is not where the gap comes from. Every committed $b_h$ lies on the decile grid (True) and the boundary's argmax does not (True), with the nearest committed values at 1/5 and 3/10. The break-even ratio rises to the argmax and falls after it, so the best available belief is the decile below.

| $b_h$ | cases | best oracle break-even | attained by |
| ---: | ---: | ---: | --- |
| 0 | 4 | $0$ (0.0000) | `a08-reaction-075` |
| 1/10 | 15 | $5/11$ (0.4545) | `a02-early-011` |
| 1/5 | 34 | $5/6$ (0.8333) | `a01-first-003` |
| 3/10 | 17 | $21/26$ (0.8077) | `a01-first-002` |
| 2/5 | 6 | $9/14$ (0.6429) | `a05-restricted-043` |
| 7/10 | 6 | $9/34$ (0.2647) | `a05-public-051` |
| 4/5 | 5 | $1/6$ (0.1667) | `a02-deep-016` |
| 9/10 | 12 | $3/38$ (0.0789) | `a04-booking-040` |

## What each question is worth

The largest break-even over the 100 cases, question by question. A question only ever gets bought below its own number.

| question | largest break-even lambda | as decimal |
| --- | ---: | ---: |
| `q_timeline` | $123/1100$ | 0.111818 |
| `q_authority` | $11/30$ | 0.366667 |
| `q_specifics` | $43/300$ | 0.143333 |
| `q_null` | $0$ | 0.000000 |

## Asking, as the ask row is repriced

| lambda | oracle asks | real asks | agrees with P2 | mean realised (real) | questions used |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1.00 | 0 | 0 | 100 | 1.650 | -- |
| 0.95 | 0 | 0 | 100 | 1.650 | -- |
| 0.90 | 0 | 0 | 100 | 1.650 | -- |
| 0.85 | 0 | 0 | 100 | 1.650 | -- |
| 0.80 | 25 | 0 | 100 | 1.650 | -- |
| 0.75 | 28 | 0 | 100 | 1.650 | -- |
| 0.70 | 41 | 0 | 100 | 1.650 | -- |
| 0.65 | 41 | 0 | 100 | 1.650 | -- |
| 0.60 | 57 | 0 | 100 | 1.650 | -- |
| 0.55 | 58 | 0 | 100 | 1.650 | -- |
| 0.50 | 58 | 0 | 100 | 1.650 | -- |
| 0.45 | 73 | 0 | 100 | 1.650 | -- |
| 0.40 | 73 | 0 | 100 | 1.650 | -- |
| 0.35 | 73 | 11 | 89 | 1.662 | q_authority |
| 0.30 | 73 | 28 | 72 | 1.800 | q_authority |
| 0.25 | 79 | 41 | 59 | 1.828 | q_authority |
| 0.20 | 79 | 41 | 59 | 1.775 | q_authority |
| 0.15 | 84 | 56 | 44 | 1.676 | q_authority |
| 0.10 | 84 | 61 | 39 | 1.522 | q_authority, q_specifics |
| 0.05 | 96 | 72 | 28 | 1.251 | q_authority, q_specifics |
| 0.00 | 96 | 72 | 28 | 1.156 | q_authority, q_specifics |

## Asking that the belief endorses and the outcome does not

_post-hoc observation, not pre-registered._ Never asking costs 1.650 per case on the labelled set. Asking is chosen and costs MORE than that at lambda 7/20, 3/10, 1/4, 1/5, 3/20, worst at 1/4. The lookahead is an expectation under the belief; where the belief is wrong the question is worth buying and wasted in outcome, and the two facts are not in conflict.

## Checks

- `grid_matches_closed_form_oracle`: **True**
- `grid_matches_closed_form_real`: **True**
- `every_real_break_even_within_oracle`: **True**
- `p2_never_asks`: **True**
- `p2_never_asks_corrected`: **True**
- `p3_act_choice_is_p2s`: **True**
- `oracle_below_analytic`: **True**
- `real_below_oracle`: **True**
- `q_null_never_pays`: **True**
- `some_posterior_does_not_factorise`: **True**
- `ec_joint` vs `costs.expected_cost` on 500 prior/action pairs: max difference 8.881784197001252e-16, agrees **True**

## Pre-registration

_a prediction: none of these values were known when it was written. Any field that reads False is the result, not a bug._

| field | predicted | measured | match |
| --- | --- | --- | :---: |
| `asks_at_lambda_1_oracle` | 0 | 0 | True |
| `asks_at_lambda_1_real` | 0 | 0 | True |
| `p3_equals_p2_at_lambda_1` | True | True | True |
| `lambda_star_oracle` | 5/6 | 5/6 | True |
| `offset_from_analytic` | 5/48 | 5/48 | True |
| `offset_cause` | belief quantization | belief quantization | True |
| `lambda_star_real_below_oracle` | True | True | True |
| `lambda_star_real_under_quarter` | True | False | False |
| `argmax_question` | q_authority | q_authority | True |
| `q_null_lambda_is_zero` | True | True | True |

All fields match: **False**
