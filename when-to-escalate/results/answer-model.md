# Expected information gain of the Gate 3 question set

An **illustration** of the answer model locked in `decisions/v2-gate3-preregistration.md`, computed by `experiments/answer_model.py` over the 100 beliefs in `results/run.json`. Offline, no API calls.

**It is not evidence about `ask`.** The impossibility result is answer-model-free: `VoI(q | b) <= V_act(b) - EC(ask | b)` follows from `V_q(b) >= 0` alone, grants a free perfect oracle, and so holds for every answer model.
Its maximum over all beliefs is `-2/13` = -0.153846 (results/voi-ceiling.json). Nothing below moves it.

## Information gain per question

Mean and range over the 100 beliefs. `IG` is in bits; the belief's own entropy is at most 2.585 bits.

| question | targets | table separable | mean IG | min | max | max at | cases with IG < 0.01 |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| `q_timeline` | readiness | True | 0.1290 | 0.0000 | 0.1540 | `a07-price-066` | 1 |
| `q_authority` | needs_human | True | 0.1278 | -0.0000 | 0.1999 | `a09-oversharer-082` | 4 |
| `q_specifics` | both | False | 0.1040 | 0.0000 | 0.1319 | `a10-early-086` | 1 |
| `q_null` | none | True | 0.0000 | -0.0000 | 0.0000 | `a02-deep-016` | 100 |

`q_null` is the control. Its answer cannot depend on the state, so its IG is 0 by the equality case in the Gate 1 definitions — an executed assertion, not a claim in prose.

A `-0.0000` in the min column is float noise, not a negative mutual information: the most negative IG anywhere in the 400 pairs is -4.44e-16, which is float rounding on a case whose true value is exactly 0. Reported rather than clamped, so a real sign error could not hide inside the tolerance.

## How much each answer couples the two axes

`IG = IG_r + IG_h + I(R ; Hh | U)`, exactly. The third term is the coupling the answer induces between readiness and needs_human, and it is what makes the OQ1 six-vector necessary: a coupled posterior does not fit in a `Belief`.

| question | mean coupling (bits) | max | cases with a coupled posterior |
| --- | ---: | ---: | ---: |
| `q_timeline` | -0.000000 | 0.000000 | 0 |
| `q_authority` | 0.000000 | 0.000000 | 0 |
| `q_specifics` | 0.004283 | 0.008493 | 96 |
| `q_null` | 0.000000 | 0.000000 | 0 |

The three separable questions sit at 0 up to float noise — a printed `-0.000000` is a value of magnitude below 1e-15, not a negative mutual information. The `separable table has zero coupling` invariant below pins it against the tolerance, and it is an independent cross-check on `separates()`: that is a rank-1 test on the table, this is an entropy computed from the posteriors, so their agreement is evidence rather than tautology.

## The adapter, both directions

- Every one of the 100 priors round-trips `Belief -> six-vector -> Belief` to within 1.11e-16.
- A coupled posterior does arise in the run: `a01-first-001`, `q_specifics`, answer `concrete` (P = 0.4488). `narrow()` raised on it: **True**.
- `Belief` is unmodified: fields are still ['needs_human', 'readiness'].

## Sweep

22 free parameters x 4 deltas = 88 variants. Unit: distinct table row, non-no_answer entry, one at a time. Perturbed entry clipped, remaining entries rescaled so the row sums to 1.

- Baseline ordering by mean IG: `q_timeline` > `q_authority` > `q_specifics`
- Order flips: **27** of 88 (11 at +/-0.05)
- Largest shift in any mean IG: 0.0786 bits
- Entries clipped to [0.01, 0.99]: 1; smallest entry after renormalisation 0.0100
- Fewest cases holding the baseline per-case ordering: 14 of 100

**Pre-registered verdict:** answer model too fragile to illustrate anything: the ordering flips under a +/-0.05 perturbation, so the illustration is withdrawn rather than repaired by choosing better entries.

This measures stability of the information-gain magnitudes (the mechanism). It does **not** measure the impossibility result, which is answer-model-free and cannot be defended or undermined by this sweep.

### Why it is fragile — post-hoc diagnosis, which does not change the verdict

| delta | variants | flips | max shift in one mean IG | flips won by > 0.002 bits |
| ---: | ---: | ---: | ---: | ---: |
| ±0.05 | 44 | 11 | 0.0341 | 9 |
| ±0.10 | 44 | 16 | 0.0786 | 14 |

The three questions' mean IGs span 0.0250 bits, while a single +/-0.05 perturbation of one entry moves one question's mean IG by up to 0.0341 bits. The ordering test was asking the sweep to resolve a signal smaller than its own step size, so the flips are decisive re-orderings rather than fourth-decimal ties: 9 of 11 flips at +/-0.05 leave the new winner ahead by more than 0.002 bits.

So the flips are not an artifact of a near-tie. The grid was pre-registered in absolute probability units and never checked against the spread of the quantity being ordered. An absolute 0.10 is 14% of a 0.70 entry and 100% of a 0.10 entry, so one grid is a mild and a total perturbation depending on where it lands. Same shape of blind spot as the Gate 2 count threshold that was not scale-free. The grid is NOT changed and the sweep is NOT re-run on a different one: §5 pre-registered this decision rule and repairing the test after seeing it fail is the thing pre-registration exists to prevent.

### What the withdrawal does and does not cover

Withdrawn: any claim that the IG ordering of these three questions means something, and any use of these IG magnitudes as a stable illustration.

Not affected, because the sweep does not bear on them:

- The invariants above. They are properties of the implementation against the Gate 1 definitions, and hold for any table.
- The OQ1 adapter, discharged on a coupled posterior that actually arose.
- The impossibility result, which is answer-model-free.

## Invariants

All 400 question-case pairs checked.

| invariant | violations |
| --- | ---: |
| ig non negative | 0 |
| q null ig is zero | 0 |
| predictive sums to one | 0 |
| ig at most h prior | 0 |
| prior entropy is additive | 0 |
| decomposition exact | 0 |
| coupling non negative | 0 |
| separable table has zero coupling | 0 |

### The free check the data hands over

Four beliefs sit at `b_h = 0.0` exactly, so `H_h = 0` and no answer can reduce it. One, `a11-repeated-097`, also has a degenerate readiness belief, so `H(b) = 0` on both axes and IG must be 0 for every question.

| case | b_h | H_r | H_h | H joint | max IG over Q |
| --- | ---: | ---: | ---: | ---: | ---: |
| `a08-reaction-075` | 0.00 | 1.1568 | 0.0000 | 1.1568 | 0.142598 |
| `a08-reaction-077` | 0.00 | 1.1568 | 0.0000 | 1.1568 | 0.142598 |
| `a11-first-095` | 0.00 | 0.4690 | 0.0000 | 0.4690 | 0.031862 |
| `a11-repeated-097` | 0.00 | 0.0000 | 0.0000 | 0.0000 | 0.000000 |

- `H_h = 0` on all four: **True**
- `IG_h = 0` on all four, every question: **True**
- `IG = 0` for every question on `a11-repeated-097`: **True**

## What this does not establish

- The answer model is **not validated**. Nothing in the data can confirm these numbers are right; the cases are single messages with no answers to fit to.
- The 22 free parameters are **(AI-proposed, Kaps-reviewed)**, not practitioner-set.
- A1 (the answer depends on the state, not the message) is false in detail and accepted for the reason given in the pre-registration.
- No claim about `ask` follows from any number here.
