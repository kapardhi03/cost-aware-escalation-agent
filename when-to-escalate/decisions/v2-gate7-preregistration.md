# Gate 7 pre-registration — the paper edit

Gate 7 folds four gates of results into 1102 lines of v1 prose that contains three
known-false claims. Prose has no test suite, so this file is it: the section map, the
sentence dispositions, the number traces, and the falsifiers are all fixed here,
before any `main.tex` edit, so that what ships can be checked against what was
promised rather than against memory.

Branch `gate7-paper`, fast-forwarded onto `origin/main` (`de189a9`, the float-fix
merge) before any section below was written. It was branched at `34173c3` and carried
no commits of its own, so the move is a fast-forward and not a replay: the paper work
sits on top of the declared tie-breaks rather than beside them. Local `main` is stale
at `7573686`, 37 commits behind, and is not the base for anything.

Row series: `Z` for this pre-registration, `AA` for the resolutions written after the
gate closes.

---

## 1. Scope, and what cannot be verified here

The paper is edited in place. v1's text is preserved by the `v1.0.0` tag at Gate 8,
not by keeping stale sentences in the file. No result is added that is not already
committed to an artifact on this branch; this gate computes nothing new.

Three environment limits, recorded so that no later claim can imply otherwise.

1. **The paper is not compiled at this gate.** `pdflatex`, `latexmk`, and `xelatex`
   are absent; `tectonic` is present with no package cache, and the network is
   blocked. Every claim made here about the paper comes from reading source, from
   `paper/figures/make_figures.py --check`, and from the test suite. "It builds" is
   Kaps's falsifier, run at the end in Overleaf or a local TeX install.

2. **`main.tex` does not compile from a clean checkout of public `main` today.**
   `paper/figures/reliability-needs-human.pdf` has never existed in git history on
   any branch — `git log --all --diff-filter=A -- 'paper/figures/*'` returns only the
   `make_figures.py` add — and `main.tex:719` includes it. V1 is therefore a build
   fix, not a cosmetic debt.

3. **V1 requires new code, so this gate is not prose-only.** `render()` in
   `make_figures.py` draws panel 1 only, writing `reliability-needs-human.{pdf,png}`.
   Panels 2 and 3 (`gate2_test_raw`, `gate2_test_calibrated`) are computed and
   `--check`-verified but have no rendering code at all.

Order of work, fixed here: the `:677` theorem subsection first and alone, since it
carries five of the sentence dispositions and the `:683` hook. Then §Results
calibration, then Method, then Limitations, then Conclusion, then the abstract, then
the figures. The abstract is written last because it quotes numbers whose final
wording is settled in the sections.

---

## 2. Result-to-section map

Eight results. Five of them land inside one 14-line subsection, because
`\subsection{Two actions that are never used}` (`main.tex:677`) is the passage that
names both unused actions, and v2 has exactly one result per action.

| # | Result | Lands in | Artifact |
|---|---|---|---|
| R1 | Impossibility theorem | `:677` subsection, rewritten and renamed | `voi-ceiling.json` |
| R2 | General condition `c_F/ν + c_T/α < 1` | same subsection, closing beat; restated in Conclusion as the portable claim | `voi-ceiling.json` `feasibility` |
| R3 | Attainment | same subsection, beat 2 | `voi-ceiling.json` `global_ceiling` |
| R4 | Depth-independence | same subsection, beat 3 | `v2-policy-boundary.md` part 3 |
| R5 | Entropy baseline | its own short subsection after it | `entropy-baseline.json` |
| R6 | Abstention | the escalate-pause half of the `:677` rewrite | `abstention.json` |
| R7 | Held-out calibration | §Results `\subsection{Calibration}` `:716`; §Method split; abstract | `logprob-elicitation.json`, `rebaseline.json` |
| R8 | Reachable-score floor `6/23` | §Results `\subsection{Calibration}`, bound to R7 | `rebaseline.json`, `make_figures.py` panel 3 |

R5 gets its own subsection rather than a paragraph inside R1's, so that the theorem
stays a theorem and the baseline stays a measurement. R1–R4 are statements about the
cost matrix and hold at every belief; R5 is a cost measured on 50 test cases at 11
pre-registered thresholds on four arms. Merging them would let a reader take the
measurement as the proof or the proof as the measurement. §Method gains the
τ-as-deciles definition, since a threshold on `H(b)` in absolute bits is the S4 shape
and the pre-registered fix — deciles of the observed `H(b)` distribution *on the arm
being scored* — has to be stated where the metrics are defined, not where they are
used.

R4 is the one result whose artifact is a decisions file rather than a JSON, because
it is a proof and not a computation. Its two premises are under test: premise A in the
`voi_ceiling` suite, premise B as invariant 6 in `tests/test_entropy_baseline.py`.
The paper cites the premises, not the prose file.

---

## 3. Sentence dispositions

Three classes, not two.

- **REPLACED** — the sentence is false and comes out.
- **KEPT-AS-LIMITATION** — true, stays, named as a scope limit v2 does not close.
- **KEPT-AND-PROVEN** — true as v1 asserted it, stays, and v2 upgrades it from
  assertion to result. Without this class a correct v1 sentence has to be filed
  either as merely kept, which loses the upgrade, or as replaced, which is false and
  ungenerous. `:681` is the case that forces it: "This is a property of the matrix
  rather than of the cases" is the impossibility theorem, asserted a year before it
  was proved.

### 3.1 The `:677` subsection — five dispositions in fourteen lines

| Lines | v1 | Disposition |
|---|---|---|
| `:678-680` | census `answer` 30, `hold` 27, `escalate-notify` 43 | KEPT — now cross-verified by a second artifact |
| `:681` | "a property of the matrix rather than of the cases" | KEPT-AND-PROVEN — this is R1 |
| `:681-683` | `ask` costs 2 against 0, and 4 against 0 | KEPT — true arithmetic |
| `:683-684` | "can only win in a narrow middle band that the quantized beliefs never land in" | **REPLACED** (V2) |
| `:684-685` | "escalate-pause is dominated by escalate-notify in every column" | KEPT-AND-PROVEN — this is R6 |
| `:685-687` | "the two unused actions are untested by this experiment" | **REPLACED** — both are now tested |
| `:687-690` | "a one-step rule cannot price ask's payoff, so the action ... is both unpriced and unused" | **REPLACED**, absorbed here |

`:683-684` is false twice, and the replacement must say both. There is no narrow
middle band on the unconstrained menu — the ceiling is negative at every belief in
the simplex, with a maximum of `−2/13` — and quantization is not the cause, since the
`raw` arm's 100 distinct beliefs leave the region just as empty. Naming only one of
the two errors leaves a reader believing a finer belief would find the band.

`:685-687` is replaced but its conclusion survives: both actions are still unused, and
v2 does not rescue either. What changes is that "untested" becomes "tested, and each
fails for a different proven reason." The census is unchanged.

`:687-690` is rewritten once, here, together with `:683-684`, and not again in the
myopia pass — the two false claims sit in the same paragraph and one rewrite serves
both.

### 3.2 The five myopia passages

Gate 6 split v1's myopia claim in two, and the halves go opposite ways. In every one
of the five passages the clause "a one-step rule cannot price asking" is
KEPT-AS-LIMITATION, because it is true and remains a scope statement about the
policy. The clause "so asking is undervalued / would earn its place if priced" is
REPLACED, because v2 priced it and it still loses, by at least `2/13` per case, on
the unconstrained menu, at every lookahead depth.

The retraction is written **once**, canonically, in Limitations at `:947`, where v1
made the claim as a limitation. The other four passages get consistency edits that
point at it. Retracting the same claim five times in five wordings is how a paper
ends up with five slightly different retractions, one of which overreaches.

| Line | Section | Disposition |
|---|---|---|
| `:249` | Related work | REPLACE "undervalues the ask action"; KEEP the one-step scope choice |
| `:343` | Agent design | KEEP "which a one-step rule cannot see"; REPLACE "poor fit ... value is mostly the better belief it buys next turn" |
| `:687` | Results | REPLACED, absorbed into the `:683` rewrite — not touched again here |
| `:947` | Limitations | the canonical retraction; REPLACE "which this design does not do", since v2 does it |
| `:1050-1058` | Conclusion | REPLACED by the answer, not by a retraction |

`:1050-1058` is the cleanest of the five and the only one that is not really a
correction. v1 asked the exact question v2 answers: "would say whether the action is
genuinely useful or merely unpriced." The answer is neither. It was priced, and it is
dominated. A question a paper poses and its successor answers is a result, and the
Conclusion should read as the question being closed rather than as v1 being caught.

The binding wording rule holds in all five: the claim is always "asking is never
rational **on the unconstrained action menu**," never the unqualified form.

### 3.3 The remaining touched sentences

| Line | v1 | Disposition |
|---|---|---|
| `:499` | "none of them falls in $(0.2, 0.3]$" | **REPLACED** (U7) — a value claim carrying the threshold bracket |
| `:728` | `fig:reliability` caption, "no case falls in $(0.2, 0.3]$" | **REPLACED** (U7) — same error in the caption |
| `:971` | the same distinction, stated correctly | KEPT — no edit |
| `:683` | see 3.1 | **REPLACED** (V2) |
| `:1043-1046` | the residual-miss floor and its cause | KEPT-AND-PROVEN (D1) |
| `:1045-1046` | "set by the granularity of the elicitation, not by the calibration method" | KEPT-AND-PROVEN — vindicated by Gate 2 |
| `:1046-1048` | "the next step is a finer-grained belief and a held-out recalibration fit" | KEPT — and it is what Gate 2 did |
| `:1060-1070` | the turn boundary | KEPT-AS-LIMITATION — untouched, and `v2-policy-boundary.md` part 4 depends on it staying |
| abstract `:100-121` | "recalibrating the marginal in-sample halves the misses, from 16 to 8" | KEPT and extended — see D4 |

U7's two false lines are a value claim wearing a threshold bracket: 17 of 100 cases
sit exactly at `0.3`, so the *value* gap is `(0.2, 0.3)`, open at both ends, while the
*threshold* interval over which every threshold decides identically is `(0.2, 0.3]`,
half-open. `make_figures.py` already draws and labels both correctly; only the prose
is wrong.

The abstract's in-sample sentence is not replaced. It is true, and v1 labelled its own
scope at `:1048` — "the numbers here are an in-sample ceiling." The held-out result
supersedes its scope rather than contradicting its content, so the sentence stays and
the held-out numbers are added next to it, under D4's denominator rule.

---

## 4. Number-to-artifact trace

Every number v2 adds to the paper, with the key path that produces it. A number that
cannot be named this way does not go in.

### 4.1 The theorem subsection

| Number | Key path in `results/voi-ceiling.json` |
|---|---|
| `α = 10`, `ν = 3`, ask row `(2, 4)` | `cost_matrix_constants` |
| `t* = 3/13 = 0.230769` | `global_ceiling.t_star_exact`, `.t_star_float` |
| `max V_act = 30/13` | `global_ceiling.max_v_act_exact` |
| `EC(ask) = 32/13` at `t*` | `global_ceiling.ec_ask_at_t_star_exact` |
| ceiling `−2/13 = −0.153846` | `global_ceiling.ceiling_exact`, `.ceiling_float` |
| witness: all-hot vertex, `b_h = 3/13`, `hold` `84/13`, `pause` `66/13` | `global_ceiling.witness_belief` |
| bound is attained | `global_ceiling.bound_is_attained` |
| monotonicity `−ν < c_T − c_F < α` asserted | `global_ceiling.monotonicity_left_branch_rises`, `.monotonicity_right_branch_falls` |
| grid crosscheck 60 steps → `−0.166667`, never exceeds; the maximum is a 1185-point plateau of 115351, not a witness | `grid_crosscheck.grid_max`, `.grid_exceeds_closed_form`, `.n_grid_points_attaining_the_max`, `.grid_points_searched`, `.grid_argmax_is_unique` |
| independent recomputation via `src.costs` agrees to 1e-9 | `witness_crosscheck.agree_to_1e_9` |
| `c_F/ν + c_T/α`: `32/30 = 16/15 > 1` | `feasibility.ratio_exact`, `.readable_condition` |
| break-even `λ = 15/16`, repriced row `(15/8, 15/4)`, 6.25% | `feasibility.break_even_lambda_exact`, `.repriced_ask_row`, `.required_reduction_pct` |
| observed per-case ceilings: 0 of 100 positive, max `−0.4000` | `per_case.n_positive_ceiling`, `.max_ceiling` |
| constrained menu: max ceiling `+1.0` at all-hot, `b_h = 0` | `constrained_regime.max_ceiling`, `.argmax` |
| positive region `b_h < 1/5`, bound by `escalate_notify` | `constrained_regime.positive_region_on_the_argmax_ray` |
| 8 constrained cases, all with `b_h ≥ 0.40`, none inside the region | `constrained_regime.n_cases_carrying_the_constraint`, `.min_b_h_among_those_cases`, `.any_such_case_inside_the_region` |

Four more, registered when the subsection was written, from
`results/voi-ceiling-arms.json` rather than `voi-ceiling.json`. The first three carry
the *second* half of V2's replacement — quantization is not the cause — which is the
half a reader is most likely to doubt, so they are registered rather than left as
prose. The fourth is the census cross-check `:678-680`'s KEPT disposition promises.

| Number | Key path in `results/voi-ceiling-arms.json` |
|---|---|
| no case has a positive ceiling on any of the four arms — 400 case-arm pairs | `per_arm.published.ceiling.all_100.n_positive_ceiling`, and the same path on `rebaselined`, `raw`, `calibrated` |
| the `raw` arm carries 100 distinct `b_h` where `published` carries 8 | `per_arm.raw.b_h.n_distinct`, `per_arm.published.b_h.n_distinct` |
| 31 raw beliefs fall below `1/5`, and 0 of those carry the constraint; the emptiness is structural on `calibrated` and contingent on the other three | `calibration_floor.consequences.no_calibrated_belief_reaches_the_positive_voi_region.n_raw_below_the_bound`, `.n_raw_below_the_bound_that_also_carry_the_constraint`, `.structural_for_the_calibrated_arm`, `.structural_for_the_other_arms` |
| census `answer` 30, `hold` 27, `escalate-notify` 43, reproduced by the VoI analysis | `per_arm.published.v_act_argmin_census` |

Attainment (R3) also cites the per-arm `V_q = 0` counts — 16 of 400 case-question
pairs on `published`, 52 on `calibrated`, 12 on `rebaselined`, 0 on `raw` — from
`results/voi-ceiling-arms.json` and the `entropy-baseline.json` arm blocks. Depth
independence (R4) cites no number of its own: it is the same `−2/13` plus
`W_k ≥ 0`.

### 4.2 The entropy baseline

All from `results/entropy-baseline.json`, key path
`arms.<arm>.threshold_sweep.thresholds[]`. 11 thresholds per arm, deciles of that
arm's own observed `H(b)`; 10 of the 11 fire on every arm.

| Number | Where |
|---|---|
| cheapest firing threshold anywhere: **+5.60**, `calibrated`, `q = 0.9`, τ = 2.3578 bits, 5 firing | `arms.calibrated.threshold_sweep.thresholds[9].realised_excess_over_v1` |
| dearest: **+128.02**, `raw`, `q = 0.0`, τ = 0, all 50 firing | `arms.raw.threshold_sweep.thresholds[0].realised_excess_over_v1` |
| per-arm cheapest: published +13.80, rebaselined +11.80, raw +7.70, calibrated +5.60 | the `q = 0.9` row of each arm |
| per-arm v1 reference totals 86 / 86 / 70 / 75 | `arms.<arm>.threshold_sweep.v1_fallback_realised_total` |
| always-ask anchor, expected: 199.62 total, 3.9924 mean | `arms.published.always_ask_anchor.gate5_all_test_cases_ask_then_act` |
| v1's committed terminal always-ask: 142 / 2.84 / 21 misses | `arms.published.always_ask_anchor.v1_always_ask_committed` |

The excess for each arm is measured against **that arm's own** v1-policy total, not
against published's 86, because v1's policy scores 70 on `raw` and 75 on
`calibrated` and charging those arms an excess against 86 would compare them to a
total they never had. The paper must carry that sentence wherever the four cheapest
numbers appear together, or the +5.60 reads as the best result when it is the best
result *on the arm with the dearest baseline*.

The §6 sentence, locked: entropy-thresholding is never free, +5.60 at the cheapest
firing threshold up to +128 asking on everything, no free threshold on any arm.

Six more, registered when §Method's τ definition was written. These are definitional
rather than results — they say what the threshold grid *is*, not what it cost — and
they are registered anyway, because a number in the paper traces whether or not it
is a finding, and because an unregistered definition is exactly where a later gate
would be free to re-choose the grid and call the old numbers comparable.

| Number | Source in `results/entropy-baseline.json` |
|---|---|
| `H(b)` spans 0 to 2.456 bits with a median of 2.017 on the run's own beliefs | `arms.published.tau_grid.observed_min_bits`, `.observed_max_bits`, `.observed_median_bits` |
| eleven thresholds at the quantiles 0.0 through 1.0 | `arms.published.tau_grid.grid[]`, eleven rows carrying `quantile` |
| eight distinct τ on the run's own beliefs, eleven on the two re-elicited ones | `arms.published.tau_grid.n_distinct_tau` = 8, `arms.raw…` = 11, `arms.calibrated…` = 11 (`rebaselined` is also 8, and the paper does not name it) |
| the grid is taken over all 100 cases of an arm, the sweep is scored on the 50 test cases, so the top decile can fire on nothing | `arms.<arm>.tau_grid.population`, `arms.<arm>.threshold_sweep.population`, `.why_the_top_decile_can_fire_on_nothing` |
| `H(b)` rounded to twelve decimals before it meets τ, derived against a measured float-noise bound | `s4_inventory.h_decimals` |
| the firing rule: ask iff `H(b) > τ`, else the cheapest action other than asking | `arms.<arm>.threshold_sweep.firing_rule`, and `.reproduces_committed_fallback: true` for the clause that this coincides with v1's action case for case |

The theoretical range `[0, log2 6] = [0, 2.585]` is arithmetic on the six-state
belief, not a key path. The `\ref` from that paragraph to R5's own subsection is
owed: the paragraph names its consumer in words, since the label does not exist
until that subsection is written, and the wiring is the same debt AC3 carried for
`sec:calibration` and AD4 discharged.

### 4.3 Calibration

| Number | Source |
|---|---|
| test raw → calibrated: CE 0.8546 → 0.8136 bits | `rebaseline.json` `calibration_claim.{raw,calibrated}.cross_entropy_bits` |
| ECE 0.1526 → 0.0696 | same, `.ece` |
| Brier 0.2063 → 0.1962 | same, `.brier` |
| base rate 0.42, label entropy 0.9815 bits | same, `.base_rate`, `.base_rate_entropy_bits` |
| distinct scores 43 → 33 | same, `.n_distinct_scores` |
| dev candidates: identity 0.9934, Platt 0.9103, isotonic 0.8356 bits | `logprob-elicitation.json` |
| elicitor: `digit_expectation` 0.9934 vs `yes_no_probability` 1.8004 dev CE | `logprob-elicitation.json` |
| `fresh_raw` 70 / 1.40 / 7 misses / `{answer 12, escalate_notify 21, hold 17}` | `rebaseline.json` `arms.fresh_raw` |
| `fresh_calibrated` 75 / 1.50 / 2 misses / `{escalate_notify 41, hold 9}` | `rebaseline.json` `arms.fresh_calibrated` |
| `rebaselined_written` 86 / 1.72 / 8 misses | `rebaseline.json` `arms.rebaselined_written` |
| `always_notify` 87 / 1.74 / 0 misses | `rebaseline.json` `belief_free_reference.always_notify` |
| reachable-score floor `6/23 = 0.260870` | `make_figures.py` panel 3 `unreachable_region`, checked against `6/23` |

Nine more, registered when the subsection was written. The table above fixes the
three proper scores and the four arms; these are the numbers the prose needed to say
*why* the scores moved and why the `answer` action vanished, which is the R7–R8
adjacency itself. Two of them — the selection margins and the map's failure to
preserve the test ranking — are costs of the committed map that the four arms do not
show. The last row is D4's own pair, quoted in §5 from `rebaseline.json` but not
registered here until the sentence that uses it was written. A tenth followed: the
escalation precision and recall of the two re-elicited arms, which is the win and its
cost as one pair of numbers, and the answer to the first question a referee asks
about a policy that escalates 41 of 50.

| Number | Key path |
|---|---|
| elicitor: `digit_expectation` 0.9934 vs `yes_no_probability` 1.8004 dev CE, a margin of 0.8071 bits | `logprob-elicitation.json` `analysis.per_elicitor.<name>.dev.cross_entropy_bits`, `analysis.elicitor_choice.reason` |
| the map rule's 0.02-bit margin, and isotonic's 0.0747-bit margin over Platt | `preregistration.map_monotone_margin_bits`, `analysis.map_choice.rule`, `.reason` |
| fitted on the 50 dev cases, scored on the 50 test cases | `analysis.calibration.fitted_on`, `.evaluated_on`, `analysis.per_elicitor.digit_expectation.{dev,test}.n` |
| the shipped map does not preserve the ranking of the test scores | `analysis.calibration.order_preserved_on_test` (`false`) |
| lowest pooled block: 23 dev cases, 6 positive, level `6/23` | `voi-ceiling-arms.json` `calibration_floor.mechanism.lowest_block` |
| the ordering `1/5 < 3/13 < 6/23`, spanning less than 0.061 end to end | `calibration_floor.ordering.as_written`, `.gaps`, `.note_on_margins` |
| exactly one of the 100 scored cases sits at the floor, and it is a dev case | `calibration_floor.reachable_range.n_cases_at_the_floor`, `.attained_by` |
| 24 of the 50 test cases below `3/13` on the raw score, 0 after the map | `make_figures.py` panels 2 and 3, `n_cases_below_threshold` |
| 16 misses on 100 cases against 8 on the 50 test cases, same policy and beliefs | `rebaseline.json` `published.all_100_reference`, `published.test` |
| escalation precision 0.667 → 0.463 and recall 0.667 → 0.905 across the two re-elicited arms | `rebaseline.json` `arms.fresh_raw.escalation_precision`, `.escalation_recall`, and the same two paths on `arms.fresh_calibrated` |

### 4.4 Figures

Three panels, from `paper/figures/make_figures.py`, populations
`{v1_needs_human: 100, gate2_test_raw: 50, gate2_test_calibrated: 50}`.

| Panel | Population | Status |
|---|---|---|
| 1 `v1_needs_human` | 100 cases, `needs_human` marginal | render code exists, never run in-repo; ECE 0.142, CI [0.100, 0.249] |
| 2 `gate2_test_raw` | 50 test cases, raw score | **no render code** — Gate 7 writes it |
| 3 `gate2_test_calibrated` | 50 test cases, calibrated score | **no render code** — Gate 7 writes it |

They are three figures and not one axis, and the script says why: the populations
differ (100 against 50), the scores differ, and only panel 3 has an unreachable
region. Plotting them together would put a 100-case in-sample curve beside two
50-case held-out curves on one pair of axes. The caption must carry the populations.

---

## 5. Danger points

Four. Labels are from the plan; the order here is by severity, so D4 comes first.

### D4 — two unrelated operations produce the same true string "16 to 8"

The worst of the four, and the only one that would have stayed invisible without
laying the numbers side by side.

v1's abstract and `:1040` both say that recalibrating the marginal in-sample "halves
the misses, from 16 to 8." That is true. The **test split also halves the misses,
from 16 to 8**, and it is not a recalibration:

    results/rebaseline.json
      published.all_100_reference   172 total   1.72 mean   16 missed escalations
      published.test                 86 total   1.72 mean    8 missed escalations

Same policy, same beliefs, same mean cost, half the case set. Two operations with
nothing in common — an in-sample recalibration of the needs-human marginal, and
restricting the population from 100 cases to the 50 test cases — produce the
identical numeric pair. A reader who meets v1's "16 to 8" and then a v2 table showing
8 misses will read the split as reproducing the recalibration gain.

The mean is scope-invariant here and the count is not, which is exactly what makes it
a trap: `1.72` may be quoted freely across the two populations, and `16 → 8` may not.

**The rule.** Every miss count in the paper carries its denominator, in the same
sentence or the same table column header. v1's in-sample `16 → 8` on 100 cases never
appears within sight of a 50-case table without one. `results/rebaseline.json`
already carries the guard — it commits `all_100_reference` next to `test` — so the
danger lives only in the prose.

This is the S4 shape again: a numeric claim whose scale the claim never states.

### D1 — the two floors, named apart before either is written

"The floor" names two different objects in this paper. They are in different units,
have different causes, and act in opposite directions. Both names are fixed here,
before either is written.

**The residual-miss floor** — v1's, at `:1043-1046`. A **count**: 8 of 16 misses
survive in-sample recalibration on 100 cases. Cause: 6 of the 7 survivors sit at
`b_h = 0.20`, in a bin whose observed frequency 0.171 is itself below `t* = 3/13`, so
no mapping of that bin to a single value can rescue them. It traps cases *below* the
threshold.

**The reachable-score floor** — Gate 4's. A **probability**: `6/23 = 0.260870`, the
positive rate of the lowest block PAVA pooled (23 dev cases, 6 positive). The
committed isotonic map cannot emit a score below it, so `[0, 6/23)` is unreachable
rather than merely unpopulated. It forbids landing *below* the threshold at all,
since `6/23 > t* = 3/13`.

Every mention of either carries its unit. They sit in different sections — the
reachable-score floor in Results with the map, the residual-miss floor in the
Conclusion where v1 put it — so the risk is cross-reference rather than adjacency.

**The upgrade inside the danger point.** v1's `:1045-1046` is a falsifiable causal
claim: the floor is set by the granularity of the elicitation, not by the calibration
method. Gate 2 tested it, by doing precisely what v1's `:1046-1048` named as the next
step — a finer-grained belief and a held-out fit — and **vindicated it**: misses go
8 → 2 on the same 50 test cases. So `:1043-1046` is KEPT-AND-PROVEN, not merely
renamed. The honest qualifier: the floor was breakable but not free. Mean cost rises
1.40 → 1.50 and escalations rise 21 → 41 of 50, and the mechanism is the
reachable-score floor, which is why R7 and R8 cannot be separated.

### D2 — `:683` is the hook, not merely an error

The false band claim is the site where the theorem replaces it. V2's own words: the
sentence is already reaching for the theorem. It asserts that `ask` can only win in a
narrow region and that the region is empty here; the theorem says the region is empty
at every belief in the simplex, on this menu, and gives the exact margin. The rewrite
is therefore an upgrade of that sentence in place, and it absorbs `:687`, so both
false claims in that paragraph are rewritten once.

### D3 — V3's separation

Discharged by D1: the two names, plus the rule that every mention carries its unit.
No sentence in the paper uses the bare word "floor" for either object.

### The required adjacency — the mirror image of a danger point

R7 and R8 **must not be separated**. Held-out calibration improves all three proper
scores — CE 0.8546 → 0.8136, ECE 0.1526 → 0.0696, Brier 0.2063 → 0.1962 — and on the
same 50 test cases it deletes the `answer` action:

    fresh_raw          {answer 12, escalate_notify 21, hold 17}   7 misses   1.40
    fresh_calibrated   {answer  0, escalate_notify 41, hold  9}   2 misses   1.50

The cause is R8. The map cannot emit below `6/23 = 0.2609 > t* = 0.2308`, so no
calibrated case can reach the region where `answer` wins, and the calibrated arm is a
two-action policy. On that arm v1's "two actions that are never used" becomes three.

Either half told alone is misleading. R7 alone is a clean win on three proper scoring
rules. R8 alone is a defect. Together they are one object: the improvement and the
reason to distrust it are the same fact, and the transferable form is that a
PAVA-fitted map's reachable range is bounded below by the positive rate of its lowest
pooled block, while cross-entropy and Brier never check that the decision thresholds
sit inside that range.

This is a falsifier, not a preference: if the shipped paper states one without the
other within the same subsection, the gate has failed.

---

## 6. The nine debts

Nine, counting Y5 as the two edits it names. Every one was recorded at the gate that
found it and deferred here, so this section is a discharge list rather than a fresh
inventory: the debt text is in `v2-design-decisions.md` at the row cited, and nothing
below widens what was owed.

| # | Debt, as recorded | What Gate 7 owes | Lands in | Row |
|---|---|---|---|---|
| V1 | `reliability-needs-human.pdf` was never committed on any branch and `render()` has never run, so the tracked `main.pdf` embeds a figure no clone can rebuild | three panels and the first PDF commit — panels 2 and 3 need render code that does not exist | `paper/figures/`, and the build itself | `:944` |
| V2 | `main.tex:683` attributes `ask`'s emptiness to a narrow band the quantized beliefs miss | replaced by the theorem, absorbing `:687` in the same rewrite | the `:677` subsection | `:945` |
| V3 | "The floor" means belief granularity at `:1045` and the map's reachable range in Gate 4 | the two names of D1, and every mention carrying its unit | Results (reachable-score), Conclusion (residual-miss) | `:946` |
| U7 | `:499` and `:728` state a value claim with the threshold bracket; `:971` is correct | both replaced, `:971` untouched | Results prose and the `fig:reliability` caption | `:856` |
| OQ3 | the self-consistency gap has no Limitations entry, only Gate 5's naming discipline | a new Limitations entry, not a hedge inside Results | Limitations | `v2-definitions.md:477` |
| X6 | attainment is a sharpening of the theorem, not a separate finding | beat 2 of the theorem subsection | the `:677` subsection | `:1053` |
| X7 | the realised inversion needs a frame that does not rest on the `rebaselined` arm | a mechanism illustration drawn off `a02-deep-017` | failure analysis or discussion | `:1054` |
| Y5a | the depth argument is proven but unstated in the paper | beat 3 of the theorem subsection | the `:677` subsection | `:1130` |
| Y5b | v1's myopia claim is made in five passages and half of it is now false | the canonical retraction at `:947`, plus four consistency edits | Limitations, and `:249`, `:343`, `:687`, `:1050` | `:1130` |

Three of the nine debts — V2, X6, Y5a — land inside the same fourteen lines, alongside
five of the eight results, which is why §1 fixes the `:677` subsection as the first
prose written and the only prose written before this document is read back. They are not
three edits to one passage but one passage with three beats, and writing them separately
is how the theorem ends up stated three times at three strengths.

V1 is the only debt that is not prose, and it is the only one that can fail silently.
The other eight are wrong sentences, which a reader of the diff can check. V1 is an
absent binary: the paper compiles for whoever has run `make_figures.py` and fails for
everyone else, which is exactly the condition v1 shipped in. So V1's discharge is not
"the panels are written" but "the PDF is committed and a clean clone builds," and the
build is Kaps's falsifier from §1 rather than mine to assert.

OQ3 is the one debt whose discharge is a subtraction. Gate 1 resolved it to a
Limitations entry and Gate 5 held the naming line — self-consistency, never validation,
never out-of-sample — but no entry exists yet, so the gap currently lives only in
`decisions/`. Writing it into Limitations is what makes the absence of external
validation a property of the paper rather than of the record behind it. S1 already
corrected OQ3's own framing once — the impossibility result is answer-model-free and
needs no defence from the Gate 3 sweep — and that correction stays where S1 put it,
in the design record, rather than being folded back into OQ3's text.

---

## 7. What would make this gate false

Stated in advance, so the failure is recognisable rather than absorbable. The first is
new at this gate and comes from the float fix.

- **The oracle/IG agreement stat appearing without its tie-break count.** "The oracle
  agrees with argmax-IG on 29 of 50 test cases" may never appear in the paper, or in
  any artifact prose, without the tie-break count in the same sentence or the same
  table row. The rule covers every arm, not just the one the paper quotes, from
  `arms.<arm>.question_selection` in `results/entropy-baseline.json`:

      published     agrees 29 of 50    needed the tie-break 13 of 50
      rebaselined   agrees 27 of 50    needed the tie-break 13 of 50
      raw           agrees 26 of 50    needed the tie-break 12 of 50
      calibrated    agrees 48 of 50    needed the tie-break  8 of 50

  Declaring the tie-break is what exposed that roughly a quarter of those agreements
  are decided by the tie-break rather than by the two rules selecting alike, so the
  stat can no longer be cited as evidence that the rules are similar — on a tied case
  the comparison has no content. This is D4's shape exactly: a numeric claim whose
  scale the claim never states. `calibrated`'s 48 of 50 is the most citable and the
  most exposed, since it is the arm most likely to be read as the rules agreeing.
- The grid crosscheck cited with an argmax point. Its maximum is attained on 1185 of
  115351 points, so the crosscheck's content is "a dumb float grid gets to `−0.166667`
  and never exceeds the closed form," not "and it happens at this belief." Naming a
  point implies a uniqueness the artifact now explicitly denies.
- Any miss count without its denominator, and in particular v1's in-sample `16 → 8`
  on 100 cases appearing within sight of a 50-case table without one (D4).
- The bare word "floor" used for either object, or a mention of either without its
  unit — a count of misses, or a probability (D1, V3).
- R7 stated without R8 inside the same subsection, or R8 without R7. The improvement
  and the reason to distrust it are one fact.
- The unqualified claim that asking never helps. The claim is always "asking is never
  rational **on the unconstrained action menu**," with the constrained-menu positive
  region `b_h < 1/5` on the hot ray stated explicitly.
- The structural-versus-contingent emptiness distinction dropped or blurred: on
  `calibrated` the region is unreachable by construction, because the isotonic map's
  range starts at `6/23 > 1/5`; on the other three arms it is merely unoccupied.
- The theorem's scope drifting into "no interaction design could justify asking." It
  bounds the value of one more question inside a deeper policy on this matrix and this
  menu.
- Invariant 6, or the depth argument's premise B, presented as independent evidence
  for the bound. Both follow from the non-negativity of `costs.COST` alone. §4 writes
  the invariant up as an analytic consequence, and dressing its triviality as a
  finding is the failure — it is load-bearing *because* it is trivial.
- `V(b^u)` called "two-step" anywhere. It is not `W_2`; it is a policy that believes
  the second question's follow-up is free.
- Any comparison of a quantity in bits to a quantity in cost points, or τ restated in
  absolute bits rather than as deciles of the observed `H(b)` on the arm being scored.
- The four per-arm cheapest excesses — published +13.80, rebaselined +11.80, raw
  +7.70, calibrated +5.60 — printed together without the sentence that each is
  measured against that arm's own v1-policy total. Without it, +5.60 reads as the best
  result when it is the best result on the arm with the dearest baseline.
- U7's two brackets swapped or collapsed: the *value* gap is `(0.2, 0.3)`, open at
  both ends because 17 of 100 cases sit exactly at `0.3`; the *threshold* interval over
  which every threshold decides identically is `(0.2, 0.3]`.
- Any number in the paper that cannot be named by a key path in §4, or a §4 trace that
  turns out not to resolve in the committed artifact.
- A figure caption without its population, or the three panels merged onto one pair of
  axes — 100 in-sample cases beside two 50-case held-out curves.
- A reproducibility claim in the paper that does not carry the interpreter floor. AB6
  closed exactly this gap in the README; restating byte reproduction in the paper
  without Python 3.12 reopens it, and it is the same class as v1's unrecorded model id.
- The retraction of v1's myopia claim written more than once. Five wordings is how one
  of them overreaches; it is canonical at `:947` and referenced elsewhere.
- The abstract's in-sample sentence deleted rather than kept and extended. It is true,
  and v1 labelled its own scope at `:1048`.
- The self-consistency check called a validation, or described as out-of-sample,
  anywhere in the paper.
- Anything computed at this gate. No new number, no edit to a committed artifact, no
  API call. A result that appears in the paper and in no artifact on this branch is the
  clearest possible failure of this document.
- Any framing of this work as coursework, as a scheduled unit of delivery, or as a
  submission — in the paper, the repository, a filename, or a commit message. This is a
  standalone research repository and the paper is a preprint.

The one falsifier this document cannot check for itself is the build. `pdflatex`,
`latexmk` and `xelatex` are absent and the network is blocked, so "it compiles, and the
figure it embeds was rebuilt from `results/run.json` in a clean clone" is Kaps's to run.
Everything else above is checkable by reading the shipped `main.tex` against this file.

---

## Provenance index, Gate 7 pre-registration

| # | Decision | Provenance | Status |
| --- | --- | --- | --- |
| Z1 | The paper is edited in place; v1's text is preserved by the `v1.0.0` tag at Gate 8, not by keeping stale sentences. Nothing is computed at this gate | (Kaps-decided) | **confirmed** |
| Z2 | Order of work is fixed before any prose: the `:677` theorem subsection first and alone, then Results calibration, Method, Limitations, Conclusion, abstract, figures. The abstract is last because it quotes numbers the sections settle | (Kaps-decided) | **confirmed** |
| Z3 | Three disposition classes, not two — REPLACED, KEPT-AS-LIMITATION, KEPT-AND-PROVEN. `:681` forces the third: v1 asserted the impossibility theorem a year before it was proved, and filing that as merely kept or as replaced would both be wrong | (AI-proposed) | **confirmed** |
| Z4 | R5 gets its own subsection rather than a paragraph inside R1's, so the theorem stays a theorem and the baseline stays a measurement | (AI-proposed) | **confirmed** |
| Z5 | `:683-684` is false twice and the replacement states both errors: there is no narrow band on the unconstrained menu, and quantization is not the cause since the `raw` arm's 100 distinct beliefs leave the region equally empty | (AI-proposed) | **confirmed** |
| Z6 | The myopia retraction is written once, canonically, in Limitations at `:947` where v1 made the claim; the other four passages get consistency edits pointing at it | (AI-proposed) | **confirmed** |
| Z7 | The binding wording rule holds in every passage: "asking is never rational on the unconstrained action menu," with the constrained positive region and its emptiness stated, and the structural-versus-contingent distinction kept explicit | (Kaps-decided) | **confirmed** |
| Z8 | D4's rule: every miss count in the paper carries its denominator. The in-sample recalibration and the test split both produce "16 to 8" and have nothing in common; the mean 1.72 is scope-invariant and the count is not | (AI-proposed) | **confirmed** |
| Z9 | D1's rule: the residual-miss floor (a count, 8 of 16 on 100 cases) and the reachable-score floor (a probability, `6/23`) are named apart, and no sentence uses the bare word "floor" for either. This discharges V3 | (AI-proposed) | **confirmed** |
| Z10 | R7 and R8 must appear in the same subsection. Held-out calibration improves all three proper scores and deletes the `answer` action on the same 50 cases, and the cause of the second is the first's map. A paper stating one without the other has failed the gate | (AI-proposed) | **confirmed** |
| Z11 | The abstract's in-sample sentence is kept and extended, not replaced: it is true and v1 labelled its own scope at `:1048`, so the held-out result supersedes the scope rather than contradicting the content | (AI-proposed) | **confirmed** |
| Z12 | Each arm's entropy-threshold excess is measured against that arm's own v1-policy total, and the sentence saying so travels with the four cheapest numbers wherever they appear together | (Kaps-decided) | **confirmed** |
| Z13 | U7's two lines are replaced with the value gap `(0.2, 0.3)` open at both ends and the threshold interval `(0.2, 0.3]` half-open; `:971` is already correct and is not touched | (AI-proposed) | **confirmed** |
| Z14 | Three figure panels, never merged onto one axis, each caption carrying its population. V1 requires new render code for panels 2 and 3, so this gate is not prose-only, and its discharge is a committed PDF plus a clean-clone build | (AI-proposed) | **noted** |
| Z15 | The oracle/IG agreement stat may never appear without its tie-break count, on any arm — 29/13 published, 27/13 rebaselined, 26/12 raw, 48/8 calibrated, all of 50. It can no longer be cited as evidence that the two selection rules are similar, because on the tied cases the comparison has no content. D4's shape, found by the float fix | (Kaps-decided) | **confirmed** |
| Z16 | The paper is not compiled at this gate: `pdflatex`, `latexmk` and `xelatex` are absent, `tectonic` has no package cache, and the network is blocked. "It builds" is Kaps's falsifier, and no claim here may imply otherwise | (AI-proposed) | **noted** |
| Z17 | OQ3's Limitations entry is written at this gate as its own entry rather than a hedge inside Results, keeping Gate 5's naming discipline; S1's correction to OQ3's framing stays in the design record and is not folded back into OQ3's text | (AI-proposed) | **confirmed** |
| Z18 | The grid crosscheck is cited as a plateau, never as a witness: 1185 of 115351 points attain the maximum, so the paper reports that a dumb float grid reaches `−0.166667` without exceeding the closed form, and names no belief. Same origin as Z15 | (Kaps-decided) | **confirmed** |
