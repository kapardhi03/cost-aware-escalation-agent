# Logprob elicitation — continuous `needs_human` scores

Generated 2026-08-24T14:26:39.024397+00:00 · 100 cases · 0 calls, 200 cache hits

## Elicitors

Cross-entropy, ECE and Brier are on `dev` — the selection split. Distinct scores and median top-1 are over all cases, because the collapse check is a property of the elicitor rather than of a split.

| elicitor | n dev | dev CE (bits) | dev ECE | dev Brier | distinct scores | median top-1 | collapsed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| `digit_expectation` | 50 | 0.9934 | 0.1616 | 0.2294 | 85 | 0.7731 | no |
| `yes_no_probability` | 50 | 1.8004 | 0.3352 | 0.3224 | 19 | 1.0000 | no |

Chosen: **digit_expectation** — lower dev cross-entropy by 0.8071 bits, outside the 0.01 margin
Rule (pre-registered): collapse disqualifies; then lowest dev cross-entropy in bits; ties within 0.01 bits go to lower ECE

## Calibration maps, fitted on dev

| map | dev CE (bits) | dev ECE | dev Brier | order-preserving |
| --- | ---: | ---: | ---: | :---: |
| `identity` | 0.9934 | 0.1616 | 0.2294 | yes |
| `isotonic` | 0.8356 | 0.0859 | 0.2026 | no |
| `platt` | 0.9103 | 0.1086 | 0.2178 | yes |

Chosen: **isotonic** — isotonic beats the best order-preserving map (platt) by 0.0747 bits, more than the 0.02 margin, so the merge is worth it
Rule (pre-registered): lowest dev cross-entropy in bits, except that an order-preserving map is kept unless a merging map beats it by more than 0.02 bits (resolution R7)

## Held-out result — fitted on dev, evaluated on test

| metric | raw | calibrated |
| --- | ---: | ---: |
| cross-entropy (bits) | 0.8546 | 0.8136 |
| ECE | 0.1526 | 0.0696 |
| Brier | 0.2063 | 0.1962 |

Test base rate 0.42, whose entropy is 0.9815 bits — the score a constant predictor gets.
Score ordering preserved on test: **no**

## Temperature-0 reproduction check (elicitor A against v1's cache)

89/100 written values match v1's cached belief exactly (89.00%); 11 drifted.

| case | v1 | re-elicited |
| --- | ---: | ---: |
| `a02-deep-016` | 0.8 | 0.7 |
| `a02-deep-017` | 0.3 | 0.2 |
| `a03-followup-024` | 0.3 | 0.2 |
| `a04-booking-035` | 0.1 | 0.2 |
| `a04-booking-040` | 0.9 | 0.3 |
| `a07-internals-068` | 0.4 | 0.7 |
| `a10-early-087` | 0.4 | 0.6 |
| `a10-persistent-091` | 0.2 | 0.4 |
| `a10-persistent-094` | 0.2 | 0.3 |
| `a11-first-095` | 0.0 | 0.2 |
| `a11-repeated-100` | 0.1 | 0.2 |
