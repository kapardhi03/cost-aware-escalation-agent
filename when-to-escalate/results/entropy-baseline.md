# The cost of thresholding on entropy, and the first VoI numbers

The cost of the entropy-threshold ask baseline, on four belief arms over the pre-registered decile grid for tau, and the first per-case VoI computation in this project.

Pre-registered in `decisions/v2-gate5-preregistration.md`.

## The sign is committed, the magnitude is the result

Every excess reported here is positive because all 400 committed per-case ceilings are negative and the unconstrained-menu maximum is -2/13 in closed form. This gate reproduces the sign as a regression guard and quantifies the magnitude.

New here: The firing index set per threshold, the cost magnitude, the first computed V_q and VoI, and the finding that the committed ceiling is attained exactly on some pairs rather than merely bounding them.

## The cost-side adapter

src.questions.narrow raises NonFactorisingError on a coupled posterior rather than projecting onto its marginals, so costs.expected_cost cannot be evaluated on one at all. q_specifics produces coupled posteriors on real cases (results/answer-model.json adapter.coupled_example).

`ec_joint` against `costs.expected_cost` on 500 (prior, action) pairs: max delta 0.

## Invariants, against computed VoI rather than the bound

| arm | pairs | inv 2 min slack | inv 3 max resid | inv 4 constant argmin | inv 6 min slack | bound attained |
| --- | --- | --- | --- | --- | --- | --- |
| `published` | 400 | -2.22e-16 | 1.11e-16 | 234 | 0 | 16 |
| `rebaselined` | 400 | -4.44e-16 | 1.11e-16 | 235 | 0 | 12 |
| `raw` | 400 | -4.44e-16 | 1.11e-16 | 236 | 8.54e-08 | 0 |
| `calibrated` | 400 | -4.44e-16 | 1.11e-16 | 253 | 0 | 52 |

**What invariant 6 actually tests.** Less than it looks. Substituting VoI = V_act - EC_ask - V_q into the slack (V_act - EC_ask) - VoI cancels both other terms and leaves V_q, measured above as agreeing to 7.77e-16. So on these definitions the invariant reduces to V_q >= 0, which holds because every entry of costs.COST is non-negative. It confirms the implementation is self-consistent; it is not independent evidence for the bound.

**Where the independent check is.** ceiling_agreement, which compares the recomputed EC(ask | b) - V_act(b) against the per-case ceilings committed in results/voi-ceiling-arms.json, and recovers V_act a second way via ceiling + EC(ask). That is what ties this gate's new code to Gate 4's analytic result. It is the check invariant 6 was meant to be: a different invariant, the same intended outcome — this gate's computed VoI held against Gate 4's committed ceiling, per arm, under ceiling_agreement above.

| arm | recomputed vs committed ceiling | EC(ask) vs 2+2b_h | V_act recovery |
| --- | --- | --- | --- |
| `published` | 0 | 4.44e-16 | 2.22e-16 |
| `rebaselined` | 0 | 8.88e-16 | 2.22e-16 |
| `raw` | 0 | 8.88e-16 | 2.22e-16 |
| `calibrated` | 0 | 8.88e-16 | 2.22e-16 |

**The bound is attained.** V_q = 0 exactly on these pairs, so the ceiling is reached rather than merely bounding. A free perfect oracle driving the post-answer expected cost to zero still loses by the full -ceiling, which means the bound's negativity cannot be attributed to slack in the bound.

Where the non-ask argmin is the same whatever the answer, the answer cannot change the action, so V_q == V_act exactly and the whole ask price is wasted: VoI = -EC(ask | b).

## Invariant 8

Identity g and Q empty reproduce v1's decisions on all 100 cases. Without it the comparison is not provably isolating the ask decision. Compared on 100 cases, 0 mismatches, tie-break v1 legacy (ACTIONS order).

Recomputed test aggregate `86` total, mean `1.72` — equal to the committed row.

## Firing counts and cost per threshold

tier1 and tier2 are expected cost under the belief. Tier 1 is answer-model-free because V_q >= 0 for any answer model; tier 2 uses the Gate 3 table.

realised_total_cost scores against the labels, exact in expectation over the answer, and is the only column comparable to v1's committed total. An expected excess added to a realised total would be neither.

### `published`

v1's policy on this arm's beliefs, same 50 cases: 86 total, mean 1.72 — reproduces results/rebaseline.json published.test. The excess column is measured against this arm's own total, which is why raw and calibrated are not charged against published's 86.

| quantile | tau (bits) | firing | tier 1 total | tier 2 total | realised total | realised excess |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 0.0000 | 50 | 65.7200 | 112.7058 | 199.62 | +113.62 |
| 0.1 | 1.6258 | 37 | 33.2200 | 74.3580 | 169.12 | +83.12 |
| 0.2 | 1.6258 | 37 | 33.2200 | 74.3580 | 169.12 | +83.12 |
| 0.3 | 1.8787 | 33 | 29.9600 | 67.0492 | 159.20 | +73.2 |
| 0.4 | 2.0174 | 14 | 15.8600 | 32.9900 | 126.60 | +40.6 |
| 0.5 | 2.0174 | 14 | 15.8600 | 32.9900 | 126.60 | +40.6 |
| 0.6 | 2.0174 | 14 | 15.8600 | 32.9900 | 126.60 | +40.6 |
| 0.7 | 2.0381 | 11 | 13.5000 | 26.9400 | 115.60 | +29.6 |
| 0.8 | 2.0829 | 11 | 13.5000 | 26.9400 | 115.60 | +29.6 |
| 0.9 | 2.2522 | 6 | 9.0000 | 16.6200 | 99.80 | +13.8 |
| 1.0 | 2.4564 | 0 | 0.0000 | 0.0000 | 86.00 | 0 |

### `rebaselined` — cache-drift column, carries no claim

v1's policy on this arm's beliefs, same 50 cases: 86 total, mean 1.72 — reproduces results/rebaseline.json arms.rebaselined_written. The excess column is measured against this arm's own total, which is why raw and calibrated are not charged against published's 86.

| quantile | tau (bits) | firing | tier 1 total | tier 2 total | realised total | realised excess |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 0.0000 | 50 | 63.7200 | 111.9280 | 195.64 | +109.64 |
| 0.1 | 1.6258 | 39 | 36.6200 | 79.5768 | 159.12 | +73.12 |
| 0.2 | 1.6258 | 39 | 36.6200 | 79.5768 | 159.12 | +73.12 |
| 0.3 | 1.8787 | 34 | 32.9600 | 70.7480 | 153.20 | +67.2 |
| 0.4 | 2.0174 | 15 | 18.2600 | 36.1800 | 120.60 | +34.6 |
| 0.5 | 2.0174 | 15 | 18.2600 | 36.1800 | 120.60 | +34.6 |
| 0.6 | 2.0174 | 15 | 18.2600 | 36.1800 | 120.60 | +34.6 |
| 0.7 | 2.0381 | 12 | 15.9000 | 30.1300 | 109.60 | +23.6 |
| 0.8 | 2.1017 | 11 | 15.5000 | 28.6100 | 113.60 | +27.6 |
| 0.9 | 2.2522 | 5 | 6.5000 | 13.2200 | 97.80 | +11.8 |
| 1.0 | 2.4564 | 0 | 0.0000 | 0.0000 | 86.00 | 0 |

Between quantiles 0.7 and 0.8 the firing count falls 12 to 11 and the realised total rises 109.60 to 113.60.
- `a02-deep-017` stopped firing: v1 plays `answer` for realised 10, ask-then-act realised 6.00, so dropping it costs +4.00. Its expected tier-1 excess is still +0.4000.

A case left the firing set and v1's realised cost on it was dearer than ask-then-act's, so the total rose while the firing count fell. Expected cost is what the ceiling bounds; a single realised draw can go either way, and here it does.

### `raw`

v1's policy on this arm's beliefs, same 50 cases: 70 total, mean 1.4 — reproduces results/rebaseline.json arms.fresh_raw. The excess column is measured against this arm's own total, which is why raw and calibrated are not charged against published's 86.

| quantile | tau (bits) | firing | tier 1 total | tier 2 total | realised total | realised excess |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 0.0000 | 50 | 63.3687 | 113.7690 | 198.02 | +128.02 |
| 0.1 | 1.6568 | 47 | 54.8886 | 104.1664 | 188.02 | +118.02 |
| 0.2 | 1.7659 | 40 | 40.1141 | 84.2742 | 159.50 | +89.5 |
| 0.3 | 1.9293 | 36 | 35.0162 | 75.4632 | 154.54 | +84.54 |
| 0.4 | 1.9898 | 31 | 30.9084 | 66.1622 | 140.98 | +70.98 |
| 0.5 | 2.0081 | 25 | 26.5625 | 55.3038 | 124.74 | +54.74 |
| 0.6 | 2.0236 | 19 | 23.1092 | 45.3109 | 122.84 | +52.84 |
| 0.7 | 2.0487 | 16 | 21.1265 | 39.9735 | 111.88 | +41.88 |
| 0.8 | 2.1372 | 12 | 14.3399 | 29.4305 | 101.50 | +31.5 |
| 0.9 | 2.2810 | 5 | 6.9054 | 13.2564 | 77.70 | +7.7 |
| 1.0 | 2.4798 | 0 | 0.0000 | 0.0000 | 70.00 | 0 |

### `calibrated`

v1's policy on this arm's beliefs, same 50 cases: 75 total, mean 1.5 — reproduces results/rebaseline.json arms.fresh_calibrated. The excess column is measured against this arm's own total, which is why raw and calibrated are not charged against published's 86.

| quantile | tau (bits) | firing | tier 1 total | tier 2 total | realised total | realised excess |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 0.7219 | 50 | 64.7656 | 121.0544 | 193.98 | +118.98 |
| 0.1 | 1.1568 | 44 | 40.7656 | 97.0544 | 169.98 | +94.98 |
| 0.2 | 2.0233 | 42 | 38.5675 | 92.2652 | 161.50 | +86.5 |
| 0.3 | 2.0720 | 35 | 31.1688 | 76.7623 | 145.90 | +70.9 |
| 0.4 | 2.1260 | 31 | 27.6315 | 68.2521 | 130.60 | +55.6 |
| 0.5 | 2.2029 | 26 | 24.1943 | 58.5458 | 126.00 | +51.0 |
| 0.6 | 2.2055 | 19 | 19.4782 | 45.0368 | 109.50 | +34.5 |
| 0.7 | 2.2448 | 16 | 17.3787 | 39.1548 | 106.80 | +31.8 |
| 0.8 | 2.2953 | 10 | 10.9207 | 24.5232 | 92.30 | +17.3 |
| 0.9 | 2.3578 | 5 | 6.5514 | 13.5927 | 80.60 | +5.6 |
| 1.0 | 2.4855 | 0 | 0.0000 | 0.0000 | 75.00 | 0 |

## The always_ask anchor

Terminal pricing charges the ask and stops; ask-then-act charges the ask and then the action the answer selects. Equality on every case would mean the follow-up is free everywhere, which is a bug.

v1 terminal: 142 total, mean 2.84. Ask-then-act on the same 50 cases: 199.62 total, mean 3.9924.

## Self-consistency

**self-consistency check of the implementation.** The answer is simulated from the same P(u | s) that produced the prediction, so this is circular with respect to the answer model by construction. It checks arithmetic, not reality.

Exact expectation 199.62, Monte Carlo mean over 2000 draws 199.607, delta 0.013. Seed 20260826. The seed makes the number reproducible. It does nothing about the circularity above and is not offered as if it did.

## Question selection

Oracle: argmax_q VoI(q | b) over the three real questions. It agrees with argmax-IG on 29 of 50 test cases.

answer-model-dependent and ordering-fragile: 27 of 88 sweep variants flip the IG ordering of these three questions (results/answer-model.md), so it carries no headline.

IG identically 0 at full ask price, so an oracle allowed to pick it could choose a dominated question. Kept in by_question as the zero-information reference.

