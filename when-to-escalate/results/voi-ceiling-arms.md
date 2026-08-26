# The answer-model-free ceiling on four belief arms

Beliefs: 100 cases per arm, 4 arms. Claim split: `test`; dev is where map selection happened and is labelled in-sample throughout.

- `published` — results/run.json
- `rebaselined` — data/logprob_cache.json written digit + fresh readiness
- `raw` — results/logprob-elicitation.json raw + fresh readiness
- `calibrated` — results/logprob-elicitation.json calibrated + fresh readiness

rebaselined, raw and calibrated share one fresh readiness vector and differ only in needs_human, so each contrast isolates the belief component that changed. published differs from rebaselined in readiness too, being the committed Gate 1 run.

## 1. The calibration floor

The committed isotonic map cannot emit a score below 6/23 = 0.260870, and both thresholds that would let `answer` or `ask` fire sit below that floor, so under this calibration neither can ever fire.

| | exact | float | what it is |
|---|---|---|---|
| positive-VoI region bound | `1/5` | 0.200000 | b_h below which the constrained-menu ceiling is positive, on the argmax ray |
| t\* (answer/notify crossover) | `3/13` | 0.230769 | nu/(alpha+nu), where answer stops beating escalate_notify |
| the map's floor | `6/23` | 0.260870 | the lowest score the committed map can emit |

`1/5 < 3/13 < 6/23`. All three numbers lie within 0.061 of each other, which is why they are carried as exact rationals: at 2dp the ordering is invisible.

**Mechanism.** PAVA sets each pooled block's level to that block's positive rate, so the first knot's y is the lowest pooled block's positive rate. The lowest block pooled 23 dev cases carrying 6 positives, so its level is `6/23`. All 12 blocks were recovered from the committed knots and the committed dev scores without refitting, and every level was checked against its own `positives / n`; the blocks cover 50 dev cases with 21 positives, a base rate of `21/50`.

| block | left edge | dev cases | positives | level |
|---|---|---|---|---|
| 0 | 2.84533e-08 | 23 | 6 | `6/23` |
| 1 | 0.228546 | 3 | 1 | `1/3` |
| 2 | 0.259318 | 13 | 5 | `5/13` |
| 3 | 0.664215 | 2 | 1 | `1/2` |
| 4 | 0.749757 | 2 | 1 | `1/2` |
| 5 | 0.796401 | 1 | 1 | `1` |
| 6 | 0.807731 | 1 | 1 | `1` |
| 7 | 0.812428 | 1 | 1 | `1` |
| 8 | 0.881208 | 1 | 1 | `1` |
| 9 | 0.888987 | 1 | 1 | `1` |
| 10 | 0.899145 | 1 | 1 | `1` |
| 11 | 0.899634 | 1 | 1 | `1` |

**Reachable range.** `[6/23, 1]` = [0.260870, 1.000000]. Knot y-values are non-decreasing and prediction is continuous and piecewise linear between them with clamping outside, so the image of R is exactly [y_first, y_last]. An isotonic fit carries no information about a region it never saw; extrapolating a slope there would be fabrication. Flatness is also what makes the floor a bound on the whole real line rather than only on the fitted interval.

The floor is attained by 1 case (`a11-repeated-097`, dev). Attainment needs a raw score at or below the first knot's x. Interpolation lifts the other cases in the lowest block strictly above the floor, so few cases sit exactly on it even though 23 dev cases were pooled to produce it. The bound is on the range, not a claim about how many cases land on it.

**Consequence 1 — `answer` is unreachable.** Every calibrated belief sits above t\*, so `answer` is never the cheapest non-ask action: 0 of 100 calibrated beliefs fall below t\*, against 48 raw ones. The V_act argmin census is `{'escalate_notify': 83, 'hold': 17}` calibrated versus `{'answer': 25, 'escalate_notify': 45, 'hold': 30}` raw.

**Consequence 2 — the positive-VoI region is unreachable.** The region's necessary condition is `b_h < 1/5`. 1/5 is the bound on the ray the constrained maximum sits on, so it is the most favourable direction in the simplex. A belief with b_h below it is not thereby inside the region: it must also carry `no_direct_answer` and lie near that ray. The sufficient test is the per-case ceiling with constraints applied, reported per arm, and it is negative on all 400 case-arm pairs.

The lowest calibrated belief is 0.260870, so 0 calibrated beliefs meet even the necessary condition, against 31 raw ones — of which 0 also carry the constraint. For the calibrated arm the bound is unreachable by construction: no input can produce a b_h below the floor, so the necessary condition fails for every belief the map can emit. For published, rebaselined and raw the bound IS reached by beliefs on unconstrained cases, and the region stays empty only because none of those cases carries `no_direct_answer`. That is a contingent fact about this dataset, not a structural one, and the two are not merged.

**Transferable form.** For an isotonic map fitted by PAVA, the reachable range is bounded below by the positive rate of the lowest pooled block. A fixed decision threshold beneath that rate cannot fire post-calibration, however many bits of discrimination the map buys. A calibration map has a reachable range; a fixed-threshold policy has thresholds; cross-entropy and Brier score never check that the thresholds sit inside the range.

This section does not claim:
- not that calibration is harmful — the calibrated arm escalates more and misses fewer cases needing a human, which is the Gate 2 result and stands
- not that the map is misfitted — 6/23 is the correct positive rate for that block and the fit is doing what PAVA should do
- not that the unconstrained-menu impossibility depends on this — that result is analytic and holds for every belief set including uncalibrated ones
- not that 6/23 is a property of isotonic regression in general — it is the property of THIS fit on THIS dev split; what generalises is that a floor exists and equals the lowest block's positive rate

## 2. What no arm can move

`V_act(b) <= min(alpha*b_h, nu*(1-b_h))` for every belief, and `EC(ask|b)` is flat in readiness, so `max_b [V_act(b) - EC(ask|b)]` is a function of the cost matrix alone. On the unconstrained menu the claim that the impossibility survives recalibration is therefore ANALYTIC: any belief is still a belief and the maximum is already negative. It is not an empirical finding and is not presented as one.

Checked, not assumed: the sections `cost_matrix_constants`, `global_ceiling`, `witness_crosscheck`, `grid_crosscheck`, `feasibility`, `lambda_crosscheck`, `constrained_regime.max_ceiling` are identical across all four arms, compared by exact equality of json.dumps(section, sort_keys=True). The script refuses to report a contrast if they ever differ.

- unconstrained maximum over every belief: `-2/13` = -0.153846
- `ask` can ever be rational on the unconstrained menu: False
- t\* = `3/13`
- general condition ask_F/nu + ask_T/alpha < 1: ratio `16/15`, satisfied False; break-even lambda `15/16`
- on the constrained menu the maximum is +1.000000 and the positive region is `b_h < 1/5` on the hot ray, bound by `escalate_notify`

Whether any real case reaches the positive-VoI region the constrained menu opens up is the only part of section 2 an arm can change.

## 3. What each arm changes

Ceilings on the `test` split. Positive would mean asking could pay; none is.

| arm | b_h range | positive ceilings | least negative | most negative | V_act argmin census |
|---|---|---|---|---|---|
| `published` | 0.0000–0.9000 (8 distinct) | 0 / 50 | -0.4000 | -3.5000 | `{'answer': 30, 'escalate_notify': 43, 'hold': 27}` |
| `rebaselined` | 0.0000–0.9000 (9 distinct) | 0 / 50 | -0.4000 | -3.5000 | `{'answer': 29, 'escalate_notify': 44, 'hold': 27}` |
| `raw` | 0.0000–0.8996 (100 distinct) | 0 / 50 | -0.2598 | -3.4977 | `{'answer': 25, 'escalate_notify': 45, 'hold': 30}` |
| `calibrated` | 0.2609–1.0000 (84 distinct) | 0 / 50 | -0.4640 | -4.0000 | `{'escalate_notify': 83, 'hold': 17}` |

Same table on dev, which is in-sample:

| arm | positive ceilings | least negative | most negative |
|---|---|---|---|
| `published` | 0 / 50 | -0.4000 | -3.5000 |
| `rebaselined` | 0 / 50 | -0.4000 | -3.5000 |
| `raw` | 0 / 50 | -0.2966 | -3.4982 |
| `calibrated` | 0 / 50 | -0.4643 | -4.0000 |

The constrained cases, where the positive region exists at all:

| arm | cases | lowest b_h | region needs b_h below | any inside |
|---|---|---|---|---|
| `published` | 8 | 0.4000 | 0.2000 | False |
| `rebaselined` | 8 | 0.4000 | 0.2000 | False |
| `raw` | 8 | 0.4042 | 0.2000 | False |
| `calibrated` | 8 | 0.4259 | 0.2000 | False |

## 4. Regression guards

results/rebaseline.json already commits these counts, including the calibrated arm's zero `answer` decisions. Gate 4 reproduces them to show the arm loader rebuilds the same beliefs; it does not discover them. See decisions/v2-gate4-preregistration.md section 3.4.

| arm | n | computed here | committed | reproduces | tie-break matters |
|---|---|---|---|---|---|
| `published` | 50 | `{'answer': 15, 'escalate_notify': 20, 'hold': 15}` | `{'answer': 15, 'escalate_notify': 20, 'hold': 15}` | True | False |
| `rebaselined` | 50 | `{'answer': 15, 'escalate_notify': 20, 'hold': 15}` | `{'answer': 15, 'escalate_notify': 20, 'hold': 15}` | True | False |
| `raw` | 50 | `{'answer': 12, 'escalate_notify': 21, 'hold': 17}` | `{'answer': 12, 'escalate_notify': 21, 'hold': 17}` | True | False |
| `calibrated` | 50 | `{'escalate_notify': 41, 'hold': 9}` | `{'escalate_notify': 41, 'hold': 9}` | True | False |

Calibrated-arm `answer` count on `test`: 0.

