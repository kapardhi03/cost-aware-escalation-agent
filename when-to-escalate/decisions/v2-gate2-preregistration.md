# Gate 2 pre-registration — logprob elicitation and calibration

**Status: locked before any live API call.** Written and committed while
`data/logprob_cache.json` does not exist. Every choice below is fixed here so it
cannot be made after seeing the numbers and described afterwards as having been
the plan.

The rules are not only prose. Each one is a function in `src/calibrate.py` with
its thresholds as module constants, so the rule is *executed* rather than
remembered and changing it is a diff. `tests/test_calibrate.py` asserts the
prose and the constants agree (`test_preregistration_matches_the_constants_it_reports`),
which is the link that keeps this document from going stale silently.

Provenance for everything in this file: (AI-proposed), **confirmed** by Kaps in
the Gate 2 opening exchange, except where marked otherwise.

---

## 1. What is being measured, and why

v1's beliefs are a coarse grid. All 100 cases take one of **8 distinct
`needs_human` values**:

| value | 0.0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.7 | 0.8 | 0.9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cases | 4 | 15 | 35 | 17 | 6 | 6 | 5 | 12 |

Source: `results/run.json`, `rows[*].belief.needs_human`, rounded to 3 dp.

A model asked for a probability in text emits a rounded decimal. The distribution
over the digit it *would* have emitted is finer than the digit itself, and that
distribution is visible in the token logprobs. Gate 2 asks whether reading it
recovers a better-calibrated `needs_human` than the written number.

**Two elicitors are run, and the choice between them is decided by the rule in
§3.** (Kaps-decided: "Run both, pick on measured ECE" — implemented as
cross-entropy first with ECE as the in-margin tie-break, §3.)

- **`digit_expectation`** (`elicit.ELICITOR_A`) sends v1's `SYSTEM_PROMPT`
  **byte-identical**, so readiness stays comparable and the reproduction check in
  §6 is meaningful. The score is the expectation over the numeric alternatives at
  the token carrying the `needs_human` value.
- **`yes_no_probability`** (`elicit.ELICITOR_B`) asks a single yes/no question and
  takes `P(Yes) / (P(Yes) + P(No))` at the first content token.
  `elicit.NEEDS_HUMAN_CRITERION` is asserted to appear verbatim inside both v1's
  prompt and B's prompt (`test_needs_human_criterion_is_verbatim_from_v1`), so
  the two elicitors are asking about the same event.

Both run at `temperature=0` with `logprobs=True` and
`top_logprobs=elicit.TOP_LOGPROBS = 20`, which is the API ceiling.

**Coverage: all 100 cases, both elicitors.** (Kaps-decided.) 200 calls.

---

## 2. Splits

| split | n | `needs_human` label True | base rate |
| --- | --- | --- | --- |
| dev | 50 | 21 | 0.42 |
| test | 50 | 21 | 0.42 |
| all | 100 | 42 | 0.42 |

Source: `results/run.json`, `rows[*].split` and `rows[*].labels.needs_human`.
The split is the one v1 already fixed in `data/cases.json` (`split_method`); it is
not redrawn here.

```python
PREREGISTRATION["selection_split"] == "dev"
```

**Every selection in §3, §4 and §5 reads dev only.** Both maps are fitted on dev
only. Test numbers are computed once, after both selections have returned, and
are reported whatever they say.

A base rate of 0.42 has entropy **0.9815 bits**. That is what a constant
predictor scores, and it is the number any elicitor has to beat to have measured
anything. (`calibrate.entropy_bits(0.42)`; asserted in
`test_constant_predictor_scores_the_base_rate_entropy`.)

---

## 3. Elicitor selection rule — locked

`calibrate.select_elicitor`. Order of operations is fixed and is part of the
rule:

1. **The collapse check (§5) disqualifies first**, before any metric is compared.
2. Among the survivors, **lowest dev cross-entropy in bits wins**.
3. If the gap to the runner-up is **within `ELICITOR_TIE_MARGIN_BITS = 0.01`**,
   the two are treated as indistinguishable and **lower dev ECE decides**.

```python
ELICITOR_TIE_MARGIN_BITS = 0.01
PREREGISTRATION["primary_metric"]   == "cross_entropy_bits"
PREREGISTRATION["elicitor_tie_break"] == "ece"
```

Why collapse disqualifies before the metric rather than alongside it: a collapsed
elicitor can still post a respectable cross-entropy by accident, and the question
the collapse check answers is not "which number is smaller" but "did this measure
anything at all". Asserted in
`test_collapse_disqualifies_before_any_metric_is_compared`.

**If both elicitors collapse, `chosen` is `None`** and Gate 2 reports that no
elicitor recovered continuous information. That is a reportable outcome, not a
failure to be resolved by picking the least-bad option
(`test_every_elicitor_collapsing_yields_no_choice`).

The boundary: `gap <= margin` is a tie, so exactly 0.01 apart falls on the tie
side. In practice the boundary is measure-zero — `0.51 - 0.50` is
`0.010000000000000009` and lands strictly outside a 0.01 margin — so the rule
always resolves one way or the other on real data. Both sides are asserted
(`test_a_gap_exactly_at_the_margin_counts_as_a_tie`,
`test_a_gap_a_hair_above_the_margin_is_not_a_tie`).

---

## 4. Map selection rule — locked

`calibrate.select_map`. Candidates, fitted on dev only:

```python
PREREGISTRATION["map_candidates"] == ["identity", "platt", "isotonic"]
```

- **`identity`** — the raw elicited scores. The thing every fitted map has to
  beat. If identity wins, Gate 2 reports that recalibration did not help.
- **`platt`** — `p = sigmoid(a * logit(clip(x)) + b)`, two parameters by
  Newton–Raphson. **Strictly monotone whenever `a > 0`.**
- **`isotonic`** — PAVA. Weakly monotone, and it **merges** distinct scores by
  construction.

The rule is lowest dev cross-entropy, **with resolution R7's preference built
in**: an order-preserving map is kept unless a merging map beats it by more than

```python
MAP_MONOTONE_MARGIN_BITS = 0.02
```

Why the margin exists rather than taking the smaller number outright. R7 prefers a
map that preserves the ordering of the continuous scores. Isotonic destroys
ordering by design — `fit_isotonic([0.1, 0.2, 0.3], [0, 0, 1])` sends both 0.1 and
0.2 to 0.0 — and the value-of-information half of this project reads the *ordering*
of beliefs, not just their level. So a merge has a cost that cross-entropy does
not price. 0.02 bits is the stated size of that cost. Demonstrated in
`test_isotonic_can_destroy_the_score_ordering`; the margin is exercised on both
sides in `test_r7_keeps_the_monotone_map_inside_the_margin` and
`test_a_large_enough_gap_buys_the_merge`.

R7 is a preference, not a prohibition. A gap above 0.02 bits buys the merge, and
`override_applied` records which branch fired.

**Platt may be unavailable, and its absence is reported rather than absorbed.**
If the dev scores perfectly separate the dev labels, the logistic MLE diverges
and no finite `(a, b)` exists. `calibrate.fit_platt` raises
`calibrate.SeparableError` in that case and the driver records the exclusion in
`maps_excluded` in `results/logprob-elicitation.json`.

No L2 prior is added to keep the fit finite. A prior is a knob, and a knob chosen
after seeing that the fit failed is exactly the kind of decision this document
exists to prevent. If Platt is excluded and isotonic is the only candidate left,
`select_map` says so explicitly — "no candidate preserved the ordering, so R7's
preference could not be applied" — because *isotonic was chosen* and *isotonic was
all that remained* are different facts
(`test_no_order_preserving_candidate_says_so`).

---

## 5. Collapse diagnostic — locked

`calibrate.collapse_verdict`. An elicitor collapses when **both** hold:

```python
COLLAPSE_MIN_DISTINCT  = 9     # n_distinct_scores < 9
COLLAPSE_TOP1_MEDIAN   = 0.99  # median top-1 probability >= 0.99
SCORE_ROUNDING_DP      = 3     # distinctness counted at 3 dp
```

The `9` is set against the data, not chosen for effect: v1's grid has **8**
distinct values (§1), so an elicitor producing 8 or fewer has recovered nothing
it did not already have. The `0.99` says the model put essentially all its mass
on one digit, which is what "the logprobs contain no extra information" looks
like.

Both conditions are required. Few distinct values with diffuse mass is a coarse
elicitor, not a collapsed one; many distinct values with concentrated mass is a
confident one. Asserted in `test_both_conditions_are_required`.

The median rather than the mean, so one diffuse token cannot rescue an otherwise
concentrated elicitor (`test_collapse_uses_the_median_not_the_mean_top1`).

Distinctness and median top-1 are computed over **all 100 cases**, not per split.
Collapse is a property of the elicitor, not of a split.

---

## 6. Temperature-0 reproduction check — a free verification

Elicitor A sends v1's prompt byte-identical at `temperature=0`, so the
`needs_human` value it *writes* should match the value already in
`data/belief_cache.json` for the same case. `reproduction_check` in
`experiments/build_logprob_cache.py` compares them across all 100 cases and
reports `compared / matched / drifted / unparseable` plus a per-case
`drift_detail`.

**Committed in advance: drift is reported, not smoothed.** (Kaps-decided: "report
drift if it doesn't match, don't smooth it.") A non-zero drift count is a finding
about temperature-0 reproducibility across a provider-side model update, and it
goes in the report at whatever size it comes out. It does **not** disqualify
either elicitor and does **not** feed into §3 — the scores are recomputed from the
logprobs either way.

The comparison is sound because `elicit.observation_hash` is the same function as
v1's `belief.input_hash`, asserted in `test_observation_hash_matches_v1s`. Every
cache hit additionally re-checks `observation_hash` and `prompt_hash`, so a
changed message or a changed prompt shows up as a refusal rather than a silent
mismatch.

---

## 7. Metric split — what is the claim and what is not

```python
PREREGISTRATION["primary_test_metrics"]   == ["cross_entropy_bits", "ece", "brier"]
PREREGISTRATION["secondary_test_metrics"] == ["mean_cost", "escalation_misses"]
```

**Primary, and the claim: calibration quality on the test split.** Cross-entropy
in bits leads, with ECE, Brier, and the reliability diagram alongside. Bits so the
number is readable against two references — 1.0 bit is a coin flip, 0.9815 bits
is the base-rate predictor (§2).

Cross-entropy is also reported decomposed, per `decisions/v2-definitions.md`: an
irreducible within-bin label-entropy term plus a KL miscalibration term that a
perfect recalibration would remove. The decomposition is exact only when
predictions are constant inside a bin, which they are not, so `residual_bits` is
reported next to it. A large residual means the bins are too coarse to read the
two parts separately, and the report says so rather than presenting the split as
clean. Both the exact case and the inexact case are asserted
(`test_decomposition_is_exact_when_predictions_are_constant_in_a_bin`,
`test_decomposition_residual_is_nonzero_when_predictions_vary_in_a_bin`).

**Secondary, explicitly caveated, and not the claim: mean cost and escalation
misses.** (Kaps-decided, matching R5.) The reason is in the data:

| split | `cost_aware` mean cost | missed escalations |
| --- | --- | --- |
| dev | 1.72 | 8 |
| test | 1.72 | 8 |
| all 100 | 1.72 | 16 |

Source: `results/run.json`, `summaries[*].policies.cost_aware`.

The test split carries only **8 of v1's 16** escalation misses, so a change of one
or two misses is inside noise and is not evidence. The caveat travels with the
number in the code itself:

```python
PREREGISTRATION["secondary_caveat"]
# "The test split carries only 8 of v1's 16 escalation misses, so a change of
#  one or two misses is not evidence. Mean cost and miss count are reported
#  alongside the calibration metrics and are not the claim."
```

**The baseline is held out too.** (Kaps-decided: "a held-out result needs a
held-out baseline.") The comparison is against v1's `cost_aware` restricted to the
test split — mean cost 1.72, 8 misses — with the all-100 figures (1.72, 16) also
reported and labelled as the full-set reference.

---

## 8. Clipping, bins, and the two things that are not new knobs

```python
CLIP_LOW, CLIP_HIGH = 0.02, 0.98
N_BINS = 10
```

The clip bounds are **not a new parameter**. They are the constants
`belief.Belief.clipped` already documents, for the same reason: v1 has a case at
exactly `needs_human = 0.00` whose label is True, and unclipped that single case
makes mean cross-entropy infinite so no comparison is possible at all. An elicited
0.00 is a refusal to entertain the possibility, not a probability. Reused rather
than re-chosen, and asserted equal to v1's in `test_clip_bounds_match_beliefs`.

Brier is deliberately left **unclipped** — it has no logarithm, so it is the one
metric the clip cannot move (`test_brier_is_unclipped`).

Ten equal-width bins is the convention. With n=50 per split it already leaves bins
nearly empty, which is a reason to report bin counts beside the number rather than
to use more bins. **Empty bins are kept** in `reliability_bins` and in the
diagram; dropping them makes a reliability plot look better than the data supports
by hiding where there is no evidence.

---

## 9. Anchor case — labelled as illustration, not evidence

`a02-deep-018` is `needs_human` 0.3, split **dev**, label True. Its recalibrated
number is therefore **in-sample**. (Kaps-decided.) It is used to show what the
recalibration does to one case and is labelled illustration wherever it appears.
No claim rests on it.

---

## 10. What would make this document false

Recorded so the failure modes are stated before, not after.

- Any constant in §3, §4, §5 or §8 changing without this file changing with it.
  `test_preregistration_matches_the_constants_it_reports` fails in that case.
- A selection made on test, or a map fitted on test.
- A third elicitor or a fourth map added after seeing the dev numbers.
- An L2 prior, ridge, or bin count introduced to rescue a fit that failed.
- Reporting the secondary metrics without the §7 caveat.

---

## Provenance index, Gate 2 pre-registration

| # | Choice | Provenance | Status |
| --- | --- | --- | --- |
| P1 | Both elicitors run on all 100 cases; the choice between them is decided by a rule fixed before the run | (Kaps-decided) | **confirmed** |
| P2 | Elicitor A sends v1's `SYSTEM_PROMPT` byte-identical, so readiness stays comparable | (AI-proposed) | **confirmed** |
| P3 | Cross-entropy in bits is the primary metric; ECE breaks ties within 0.01 bits | (AI-proposed) | **confirmed** |
| P4 | Collapse disqualifies before any metric is compared; both elicitors collapsing yields no choice | (AI-proposed) | **confirmed** |
| P5 | Collapse thresholds are 9 distinct values and a 0.99 median top-1, set against v1's 8-value grid | (AI-proposed) | **confirmed** |
| P6 | R7's ordering preference is enforced as a 0.02-bit margin, not as a prohibition | (AI-proposed) | **confirmed** |
| P7 | `SeparableError` is raised and the exclusion reported; no L2 prior is added | (AI-proposed) | **confirmed** |
| P8 | Clip bounds are reused from `Belief.clipped`, not re-chosen | (AI-proposed) | **confirmed** |
| P9 | Temperature-0 drift against v1's cache is reported at whatever size it comes out | (Kaps-decided) | **confirmed** |
| P10 | Calibration quality is the test claim; mean cost and misses are secondary and caveated | (Kaps-decided) | **confirmed** |
| P11 | The v1 baseline is computed restricted to the test split, with all-100 kept as the full-set reference | (Kaps-decided) | **confirmed** |
| P12 | `a02-deep-018` is in dev, so its recalibrated number is labelled in-sample illustration | (Kaps-decided) | **confirmed** |
| P13 | Selection reads dev only; test metrics are computed once, after both selections return | (AI-proposed) | **confirmed** |
