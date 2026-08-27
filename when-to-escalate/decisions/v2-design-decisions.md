# v2 Design Decisions

Planning notes for v2. Each entry tagged by who proposed it and its status.

## Scope

- Recalibrate the "needs_human" belief first, then compute Value of Information(VoI) on
  top of the fixed belief. VoI is only meaningful if the belief it is computed
  under is honest, so calibration comes first.
- Carried from v1: the one-step myopic policy undervalues the `ask` action,
  because asking pays off through a better belief next turn, not through lower
  cost this step. v2 exists to price that payoff.
  **Superseded at Gate 1 — see G1 in "Resolutions after Gate 1" below.** Pricing
  the payoff is not sufficient, because the payoff is capped below the price of
  asking. The bullet is left as written rather than edited, per the
  no-retroactive-edits rule.

## Concept notes

- Expected information gain is always >= 0. A single answer can surprise you, but
  averaged over possible answers a question never raises uncertainty. Questions
  therefore split into "reduces uncertainty a lot" vs "reduces almost nothing."
  The near-zero bucket is the interesting one.
- Dropped the word "retrain." The belief comes from an LLM provider plus a
  rule-based fallback, so there are no weights to train. The real operation is
  refitting the calibration map on new labels. Named accordingly in code.

## Additions to the architecture

- Selective prediction / abstention: when entropy is high and VoI says asking
  will not help, hand the case off instead of guessing. Directly targets the
  escalation misses from v1.
- Abstention maps to the pause action (stop and hand off), not the notify action
  (alert a human while continuing).
- The information-gain scorer doubles as an active-learning acquisition function:
  the same "which question cuts entropy most" score picks which question to ask a
  user and which collected chat is most worth labeling.
- Emoji handling in two parts: first confirm whether emoji-heavy or code-switched
  inputs actually score worse before building any normalizer, then add an emoji
  reaction feature in the UI.

## Calibration data

- Human labels are the source of truth. Collect real answers, synthetic ones, and
  my own labels. My labeling step must be one click and under a minute per case.

## Belief scores

- Re-score from cache; add a few new examples only if a real gap shows up.
- Use raw scores and drop the 0.2 quantization floor. If the cache only saved the
  quantized grid, a re-scoring run is needed to capture raw values.

## UI

- Middle weight, second priority behind the model work. SQLite storage, a chat
  interface for testing and data collection, a "recalibrate on new labels"
  action, tracing, emoji reactions, and a live metric graph. Shaped like a
  standard eval/observability loop: trace log, label store, calibration monitor.

## First task

- Audit the cache before anything else: confirm whether raw pre-quantization
  scores exist, and whether emoji or code-switched inputs score worse. Both
  findings gate the work downstream.

## Tracking one case across v2

Case `a02-deep-018` is a good anchor to carry through both gates.

- Recalibration check: the model put needs_human at 0.30 on a message that reads
  much stronger than that (my own read was closer to 0.55). Right direction,
  magnitude too low. This case cleared the 0.23 threshold anyway, so the decision
  was already correct. That makes it the test that recalibration fixes magnitude
  without flipping a case that was already right. The v1 misses were the same
  under-read but sitting below the threshold, where the low magnitude actually
  cost the decision. Same gap, opposite side of the line.
- VoI check: needs_human already clears the threshold and the action is notify, so
  a clarifying question would not change the action. VoI should say do not ask
  here. This is a candidate for the "high information gain, low value of
  information" bucket, or at least a clean case where VoI correctly stays quiet.
- Produce a parallel decision record for this same case in v2: needs_human before
  (0.30) and after recalibration, plus the VoI number. One case tracked across
  both versions is a stronger story than introducing a fresh one.

## Resolutions after the cache audit

The audit corrected several premises. Recording what changed and what was decided.

- The coarse belief values are the model's own output granularity (one decimal
  from gpt-4o-mini at temperature 0), not a rounding step in the harness. The grid
  is 0.1, not 0.2; 0.2 is just the most common value. Re-running the same prompt
  reproduces the same numbers, so a naive re-scoring run recovers nothing.
- The model never emits 0.5 or 0.6 — it jumps 0.4 to 0.7. It will not express a
  near coin-flip. This matters because the highest-uncertainty cases are exactly
  the ones a VoI story needs, and the grid cannot represent them.
- Decision on scores: elicit continuous values via token logprobs (read the top
  logprobs for a single token and take the expectation), keeping the 0.1 grid as a
  no-network fallback. Continuous scores unblock both the calibration map and VoI.
  Logprob-derived scores go to a new cache file so the original cache and reported
  v1 numbers stay reproducible. This turns the audit step into a small
  data-generation step, which is the honest cost of having beliefs near 0.5 to
  reason about.
- Emoji normalizer: dropped. The four emoji cases are all the easy corner
  (needs_human False, cold or warm), there is no emoji case with needs_human True,
  and code-switching is absent from the data. The data has no power to justify a
  normalizer. The emoji reaction feature in the UI is separate and stays.
- Recalibration is not a new result. An in-sample recalibration (fit on all
  labels, an upper-bound oracle) was already run. The honest increment for v2 is a
  held-out recalibration using a genuine monotone map rather than a per-bin oracle,
  reported with cross-entropy and a reliability diagram alongside ECE. The paper
  states this framing so nothing overclaims.
- Baseline number: use the legacy 1.720 mean cost (ties broken toward answer) as
  the headline, since that is what the reported v1 results use. A safe tie-break
  variant (1.650) exists and is noted. Both agree on 16 misses.
- Tension to watch between calibration and VoI: a plain isotonic fit on the grid
  collapses distinct values into a few blocks and merges the ordering that VoI
  depends on, and it drives the answer action to zero. Prefer a calibration map
  that preserves the monotone ordering of the continuous scores over one that
  minimizes cost by merging blocks. Flag it if the two goals conflict.
- cases.json stays as is: it is synthetic, contains no real people, product, or
  client data, and was already part of v1. Synthetic domain data is standard.

### Provenance index

The bullets above carry the reasoning; this table carries only the tags the record
requires. `R`*n* is the *n*th bullet of "Resolutions after the cache audit", in
order. Status is `confirmed` (a planning assumption held), `changed` (a planning
assumption was wrong and is corrected here), or `noted` (a new fact, no plan
change). Supporting measurements are in the `## v2` section of `build-log.md`.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| R1 | Coarse values are the model's own granularity, not a harness rounding step; the grid is 0.1, not 0.2 | (AI-proposed) | **changed** |
| R2 | The model never emits 0.5 or 0.6 | (AI-proposed) | **noted** |
| R3 | Elicit continuous scores via token logprobs; 0.1 grid kept as no-network fallback; new cache file | (Kaps-decided) | **confirmed** |
| R4 | Emoji normalizer dropped; the UI reaction feature is separate and stays | (Kaps-decided) | **changed** |
| R5 | Recalibration is not a new result; the increment is a held-out fit with a genuine monotone map | (Kaps-decided) | **changed** |
| R6 | Headline baseline is legacy 1.720; safe tie-break 1.650 noted; both agree on 16 misses | (Kaps-decided) | **noted** |
| R7 | Prefer a calibration map that preserves score ordering over one that minimises cost by merging blocks | (Kaps-decided) | **noted** |
| R8 | `data/cases.json` stays as-is | (Kaps-decided) | **confirmed** |

Two findings in `build-log.md` have no bullet above because they changed no plan:
the absence of any discarded raw layer (nothing in the v1 code path ever rounded),
and the fact that v1's own records — Q6 in `build-log.md`, correction C4 in
`results/wrong-decisions.md` — had already noted the one-decimal granularity.
Both are (AI-proposed), **noted**.

---

## Resolutions after Gate 1

Gate 1 was meant to write definitions. It also produced a theorem, which changed
the scope premise. Every number referenced here traces to `results/voi-ceiling.json`,
written by `experiments/voi_ceiling.py`; the derivations are in
`decisions/v2-definitions.md`.

- **G1 — the scope premise was wrong, and this supersedes the second Scope
  bullet.** v2 was framed as pricing a payoff the myopic policy undervalues. The
  Gate 1 ceiling shows there is no payoff to price: `VoI(q | b) ≤ V_act(b) −
  EC(ask | b)`, and that ceiling is negative for every belief, every question and
  every answer model on the unconstrained action menu. `max_b V_act(b) = 30/13 =
  2.3077` against `min_b EC(ask | b) = 2`, and the two do not occur at the same
  belief. The binding constraint was the price of a question, not the horizon.
- **G2 — v1's "0 asks in 100 cases" was a necessity, not an observation.**
  `V_act == V` on 100/100, so `ask` is never even the myopic argmin. v1 read its
  own action census as evidence about the one-step horizon; it was evidence about
  the matrix. This framing carries into the paper: the census is a consequence of
  the theorem, and the theorem is what explains it.
- **G3 — the impossibility is the headline result, and the general condition is
  the transferable one.** With `ask` priced at `(c_F, c_T)`, the ceiling can be
  positive iff `c_F/ν + c_T/α < 1` — the price of a question measured against a
  needless escalation when no human is needed, plus its price against a false
  assertion when one is, must sum to under 1. v1 sits at `16/15`. This turns a
  fact about our matrix into a testable condition on any cost structure, and the
  paper frames it that way rather than as a fact about these 30 numbers.
- **G4 — v2 has two spines, not one.** (1) Calibration: the honest, held-out,
  measurably-better-agent half, unchanged from the plan and still the concrete
  improvement. (2) The impossibility theorem plus the general condition: the
  structural-discovery half. Neither is subordinate to the other and the paper
  carries both.
- **G5 — VoI stays genuinely computed, but is demoted from a shipped `ask`
  feature to the analysis that produced the theorem.** The answer model and the
  VoI machinery get built only to the depth needed to demonstrate the ceiling
  holds empirically case by case: entropy, information gain, the counterfactual
  belief update, and VoI evaluated on real cases under a simple, documented
  answer model. No production `ask` feature, and nothing is tuned to make `ask`
  fire. The point of computing VoI is to show it stays capped exactly where the
  theorem says, not to manufacture a positive case.
- **G6 — the cost matrix is not touched.** Re-pricing `ask` would reopen a locked
  v1 decision and read as goalpost-moving. The break-even scaling
  `λ = 15/16` (`ask` at `(1.875, 3.750)`, a reduction of exactly `1/16` = 6.25%)
  is computed on a local copy inside `voi_ceiling.py` and reported as a declared
  sensitivity. `voi_ceiling.py` contains no assignment into `COST`.
- **G7 — binding wording rule, in force through Gates 5–7 and the paper.** The
  claim is always *"asking is never rational **on the unconstrained action
  menu**."* Never the unqualified "asking never helps." Under `no_direct_answer`
  the ceiling reaches `+1.000` and the positive region is `b_h < 1/5` on the
  all-hot ray, bound by `escalate_notify`; that region is stated explicitly, as
  is the reason it is empty here — all 8 `a05-restricted` cases have
  `b_h ≥ 0.40`, because the archetype that forbids answering is the one where a
  human is likely needed. The theoretical claim and the empirical one are made
  separately; collapsing them would overclaim.
- **G8 — three open questions resolved, one held.** The internal posterior widens
  to a six-vector for the VoI computation while `Belief` and its 337 tests stay
  untouched (OQ1). The VoI honesty check is named a self-consistency check of the
  implementation wherever it appears, with the absence of external validation as
  a new Limitations entry (OQ3). Abstention (OQ2) is held to Gate 4, where the
  wiring is built and the cost of each option is visible rather than predicted.
  Full analysis for each is in `decisions/v2-definitions.md` §7.

### Provenance index, Gate 1

`G`*n* is the *n*th bullet above, in order. Same status vocabulary as the cache-audit
index. Supporting measurements are in `results/voi-ceiling.json` and the `## v2`
section of `build-log.md`.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| G1 | The scope premise was wrong: there is no undervalued payoff to price, because VoI is capped below the price of asking. Supersedes the second Scope bullet | (AI-proposed) | **changed** |
| G2 | v1's 0 asks in 100 cases was a necessity of the matrix, not evidence about the horizon; `V_act == V` on 100/100 | (AI-proposed) | **changed** |
| G3 | The impossibility is the headline result; the general condition `c_F/ν + c_T/α < 1` is the transferable one and the paper frames it that way | (Kaps-decided) | **confirmed** |
| G4 | v2 has two spines — calibration, and the impossibility theorem plus general condition — and the paper carries both | (Kaps-decided) | **changed** |
| G5 | VoI stays genuinely computed but is demoted to the analysis behind the theorem; no production `ask` feature, nothing tuned to make `ask` fire | (Kaps-decided) | **changed** |
| G6 | The cost matrix is not touched; the `λ = 15/16` re-pricing is a declared sensitivity on a local copy only | (Kaps-decided) | **confirmed** |
| G7 | Binding wording rule: always "on the unconstrained action menu", with the constrained-menu region and its emptiness stated explicitly | (Kaps-decided) | **noted** |
| G8 | OQ1 → six-vector posterior, `Belief` untouched; OQ3 → self-consistency check with the gap in Limitations; OQ2 → held to Gate 4 | (Kaps-decided) | **confirmed** |

One Gate 1 finding has no bullet above because it changed no plan: `t* = ν/(α+ν)
= 3/13`, the belief at which the ceiling is maximised, is the
`answer`-versus-`escalate_notify` crossover already documented in v1 rather than a
new constant. (AI-proposed), **noted**.

---

## Records integrity — two parked items closed, resolved as leave

Two items had been parked for Gate 8 because they sat where the standing
no-cohort-language rule collides with the standing no-retroactive-edits rule.
They are closed here so they do not resurface: **history integrity wins over
word-scrubbing**, and in both cases the words identify nothing. The
no-cohort-language rule governs what this project *authors* from here on, not
what its history already recorded.

- **G9 — `build-log.md` rows 1, 45 and 47 keep their wording.** They are dated
  entries in an append-only log. Editing them would falsify the record of what
  was known when, which is the one thing that log exists to preserve. Row 47 in
  particular is the entry that recorded the moved-path 404 as a known cost at the
  time, and is load-bearing evidence for the correction now carried in
  `social/x-thread.md`.
- **G10 — the 11 v1 commit messages containing `week1` / `deliverable` are not
  rewritten.** Purging them means rewriting all of v1's history, on a published
  repository, to change words that name no person, client or product. Not worth
  it, and the rewrite would itself be the larger integrity cost.
- **G11 — `v1.0.0` is tagged retroactively at Gate 8.** No tags exist in the
  repository; `v1.0.0` was never created even though v1 is complete and
  published. It gets tagged at the v1 head commit as part of the Gate 8
  reproducibility pass, before `v2.0.0`.
- **G12 — `build-log.md` row 27 keeps its wording too.** Added at the Gate 2
  close: a sweep for cohort language found a *fourth* row G9 had not enumerated.
  Row 27 (2026-08-18) reads "too many locked pieces moving at once for Week 1" in
  its Why column — the words sit in the reasoning, not in a path, which is why the
  earlier path-oriented sweep missed them. Resolved the same way as G9 and for the
  same reason: it is a dated entry in an append-only log. The transferable point is
  that G9's enumeration was a list, not a rule, so it could not catch a row nobody
  had looked at. G9 and G12 together are now the rule: **no historical
  `build-log.md` row is edited for wording, whether or not it appears in a list.**

What remains genuinely open at Gate 8 is therefore one technical item: the
`.gitignore` line 32 versus line 38 conflict, which may prevent the paper's
figure from being committed.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| G9 | `build-log.md` rows 1/45/47 keep their cohort wording; an append-only log is not edited to match a later naming rule | (Kaps-decided) | **confirmed** |
| G10 | The 11 v1 commit messages are not rewritten; history integrity beats word-scrubbing and the words identify nothing | (Kaps-decided) | **confirmed** |
| G11 | `v1.0.0` is tagged retroactively at Gate 8, before `v2.0.0` | (Kaps-decided) | **noted** |
| G12 | `build-log.md` row 27 keeps its wording; G9's list becomes a rule covering every historical row | (Kaps-decided) | **confirmed** |

## Resolutions after Gate 2a

The pre-registered choices — which elicitor, which map, the collapse threshold,
the metric split — are **not repeated here**. They live in
`decisions/v2-gate2-preregistration.md` with their own provenance index (P1–P13),
and duplicating that table into this file is how two records drift apart. What
follows is everything Gate 2a decided that the pre-registration does not cover.

- **Q1 — the elicitation cache stores raw payloads, never scores.** An extraction
  bug found after the calls have been paid for must be fixable without paying
  again, and that is only possible if the token reads survive. `--rescore`
  recomputes every number from stored payloads with zero calls. Asserted by
  `test_cache_entry_stores_the_payload_not_the_score`, which checks that the
  string `score` appears nowhere in the serialised entry.

- **Q2 — `reportable` is derived from the payload, not from the CLI flag.**
  Changed during 2a, after the original design failed. Keying `reportable` on
  `--dry-run` meant `--rescore` pointed at the dry cache produced a fully
  reportable results file out of stub payloads. Provenance now travels with the
  data (`STUB_MARKER = "offline_stub"` on every stub row) and both `reportable`
  and the output filename stem are derived from its absence. The general lesson,
  worth carrying to later gates: a provenance claim keyed on *how the program was
  invoked* is one flag away from being false, whereas one keyed on *what the data
  says about itself* survives being re-entered by a different route.

- **Q3 — `score_yes_no` scans to the first content token.** Changed during 2a. It
  read `reads[0]`, so a model emitting a leading space under `max_tokens=3` would
  have raised on entirely ordinary output. The count of skipped whitespace tokens
  is reported rather than discarded, so the condition stays visible if it turns out
  to be common.

- **Q4 — the `.gitignore` figure conflict is fixed by anchoring the scratch
  pattern, not by broadening the negation.** The root-level `figures/*` rule keeps
  its mid-pattern separator, which anchors it to the repository root and leaves
  `paper/figures/` alone. Broadening it to `**/figures/*` would re-ignore the
  figure `main.tex` needs. Also recorded: `git check-ignore -v` is **not** a valid
  "is this ignored" test, because it exits 0 on any match *including a negation*.
  The authoritative test is `git status --porcelain --ignored=matching`, where `??`
  means addable and `!!` means ignored.

- **Q5 — the reliability diagram is written after 2b, not before it.** It consumes
  2b's output, and there is nothing honest to plot from stub payloads. Its
  substance is already pre-registered (empty bins kept, counts reported alongside),
  so what remains is rendering. The `.gitignore` prerequisite is done and verified,
  so the figure will be committable the moment it exists.

- **Q6 — the 2a/2b split is a network boundary, and 2a ends with a handover.**
  Everything that can be built and verified without a paid call was built and
  verified first; the pre-registration is locked before the single 2b command is
  handed over. This is what makes "the rule was fixed before the data arrived" a
  checkable claim about the commit order rather than an assurance.

- **Q7 — the elicitation cache is written every ten calls and again on the way
  out, not once at the end.** 2b is the only step in this gate that costs money and
  cannot be repeated for free, so a failure part-way through must not discard the
  calls already paid for. The loop is wrapped in `try/finally` around a `flush()`
  that fires at `CHECKPOINT_EVERY = 10` and once more on exit, whatever the exit —
  success, an API error, or a Ctrl-C. Ten bounds the loss to ten calls for about
  twenty writes of a 1.3 MB file, which is nothing against the latency of the calls.
  `flush()` is guarded on `calls > saved_at`, which is what keeps a refusal path
  from leaving an empty cache behind for a later `--cache-only` run to serve as
  legitimate. Verified by watching the writes land at 10, 20 and 24 over 24 stub
  calls, and by crashing the loop mid-case and confirming the 7 paid calls were on
  disk. This driver has no unit tests — v1's convention for `experiments/` — so
  those two checks are ad-hoc, and the build log says so rather than implying
  coverage.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| Q1 | The elicitation cache stores raw payloads and never scores, so an extraction fix is re-runnable offline | (AI-proposed) | **confirmed** |
| Q2 | `reportable` is derived from a per-row stub marker, not from the `--dry-run` flag | (AI-proposed) | **changed** |
| Q3 | `score_yes_no` scans to the first content token and reports skipped whitespace | (AI-proposed) | **changed** |
| Q4 | Root `figures/*` stays anchored by its mid-pattern separator; `git status --ignored=matching` is the authoritative ignore test, not `git check-ignore` | (AI-proposed) | **confirmed** |
| Q5 | The reliability diagram is written after 2b, since it consumes 2b's output | (AI-proposed) | **noted** |
| Q6 | 2a is built and verified entirely offline; the pre-registration is committed before the 2b command is handed over | (Kaps-decided) | **confirmed** |
| Q7 | The cache is checkpointed every ten calls and flushed in `finally`, so a mid-run failure keeps every paid call | (AI-proposed) | **changed** |

---

## Resolutions after Gate 2b

2b made the 200 calls and ran the pre-registered rules against real data. Every
number below traces to `results/logprob-elicitation.json` or
`results/rebaseline.json`; the three-arm comparison is rendered in
`results/rebaseline.md`. As in 2a, the pre-registered rules themselves are not
restated here — they are in `decisions/v2-gate2-preregistration.md`.

- **Q8 — `digit_expectation` is the chosen elicitor, and the *metric* is what
  disqualified the alternative.** Dev cross-entropy 0.9934 bits against 1.8004,
  a gap of 0.8071 bits, far outside the 0.01-bit tie margin, so `tie_break_used`
  is `false` and ECE never came into it. This reverses the prior lean toward
  Yes/No — which was stated in discussion before the run and, notably, *never
  written into any file*, so the pre-registration is the only reason it could not
  quietly become the choice after the fact. (Kaps-decided, in discussion: "the
  method I'd have picked blind was the one that failed.") Worth stating plainly
  because it is the whole case for pre-registering: had the elicitor been picked
  on judgement rather than on a rule fixed beforehand, the worse one would have
  been picked.

  Both raw elicitors are worse on dev than a constant predictor at the base rate,
  whose cross-entropy is the label entropy 0.9815 bits: Yes/No by 0.819 bits,
  `digit_expectation` by 0.012. Reading the logprobs does not by itself produce a
  useful probability. That is what the calibration step is for, and it is why
  Gate 2's claim is the held-out *improvement* rather than the raw score.

- **Q9 — the collapse diagnostic returned `False` for both elicitors, and its
  pooled distinctness count is a blind spot that is documented rather than
  retuned.** `disqualified` is `[]`. Yes/No is the exact pathology §5 was written
  to catch — median top-1 probability 0.99999987, essentially all mass on one
  token, and a cross-entropy worse than predicting the base rate — and it cleared
  the gate, because collapse requires **both** halves and Yes/No produced 19
  distinct values against a threshold of 9. Those 19 values are residual mass,
  not recovered spread.

  The reason it cleared is specific and general. §5 fixes distinctness over **all
  100 cases**, on the stated ground that collapse is a property of the elicitor
  and not of a split. But pooling can only ever *raise* a distinct-value count,
  so the pooled form of that half is strictly the more permissive one. Running
  the pre-registered `calibrate.collapse_verdict` per split shows what that
  bought:

  | elicitor | split | distinct | median top-1 | `collapsed` |
  | --- | --- | ---: | ---: | --- |
  | `digit_expectation` | dev | 48 | 0.77778299 | `False` |
  | `digit_expectation` | test | 43 | 0.75991074 | `False` |
  | `digit_expectation` | pooled | 85 | 0.77305676 | `False` |
  | `yes_no_probability` | dev | **8** | 0.99999993 | **`True`** |
  | `yes_no_probability` | test | 14 | 0.99999983 | `False` |
  | `yes_no_probability` | pooled | **19** | 0.99999987 | `False` |

  On dev — the split the elicitor choice is actually made on — Yes/No lands on
  exactly 8 distinct values, v1's grid size, and would have been **disqualified**.
  The two splits land on different subsets of the residual values, so pooling more
  than doubled the count past the threshold. The transferable lesson: a threshold
  on a count of distinct values is not scale-free, and pooling `n` upward loosens
  it monotonically. A count threshold has to travel with the `n` it is counted
  over.

  **The thresholds are not retuned and §5 is not rewritten.** (Kaps-decided:
  documenting the blind spot beats hiding it.) The rule fired exactly as written,
  the metric caught what the diagnostic missed, and a threshold edited after
  seeing the data it governs is worth nothing. Recorded here so Gate 4 and the
  paper carry the caveat rather than the clean story.

- **Q10 — `isotonic` is the chosen map, taken within R7's margin, and
  `order_preserved_on_test: false` is carried forward as an open flag.** On dev:
  identity 0.9934 bits, Platt 0.9103, isotonic 0.8356. Isotonic beats the best
  order-preserving candidate by 0.0747 bits, more than R7's 0.02 margin, so
  `override_applied` is `false` and the merge is bought honestly. `maps_excluded`
  is empty — the `SeparableError` that dropped Platt during the dry run was an
  artifact of the stub's separable scores and did not recur on real data.

  The cost of the merge is real and is now measured rather than predicted:
  isotonic is `strictly_monotone: false` with 12 knots, six of which sit at
  1.0, and ordering is **not** preserved on test. This is the Gate 2 / Gate 4
  tension flagged at the audit, arriving exactly where R7 said it would.

- **Q11 — the 11-in-100 temperature-0 drift is recorded as unreproducible beliefs,
  not as a diagnosed cause, and it is never attributed to the calibration map.**
  Elicitor A sends v1's prompt byte-identical at `temperature=0`, so the value it
  writes should equal the value in `data/belief_cache.json`. It does for 89 of 100
  cases; 11 differ, 0 are unparseable. **What changed is not determinable from the
  record**: both runs requested the alias `gpt-4o-mini`, but v1 stored the alias it
  asked for while v2 stores the snapshot the API resolved to
  (`gpt-4o-mini-2024-07-18`), so a snapshot change between 2026-08-19 and 2026-08-24
  and serving-side nondeterminism at `temperature=0` fit the evidence equally well.
  That is a v1 record-keeping gap, and the fix — store the resolved model id, which
  v2's cache does — is already in place for every comparison from here on. Recorded
  as limitation **L10** in `build-log.md`. The consequence for this gate holds
  whatever the cause: any v1-versus-v2 cost comparison mixes the map with whatever
  moved, so `experiments/rebaseline.py` re-runs v1's decision rule on the fresh
  beliefs and the before/after is taken **within** the fresh beliefs.
  (Kaps-decided: re-baseline both sides so the contrast isolates calibration.)

- **Q12 — on the decision metrics the map is a trade-off, not a win, and Gate 2's
  claim is the calibration metrics.** Held out on test, calibration improves every
  calibration-quality measure: cross-entropy 0.8546 → 0.8136 bits, ECE 0.1526 →
  0.0696, Brier 0.2063 → 0.1962. The decomposition attributes the gain where it
  should be: miscalibration 0.1643 → 0.0988 bits.

  The decision metrics move in opposite directions. Missed escalations fall 7 → 2
  while mean cost **rises** 1.4000 → 1.5000, because the map lifts the low scores
  enough that the myopic rule escalates 41 of 50 cases instead of 21 — recall
  0.6667 → 0.9048, precision 0.6667 → 0.4634. Better-calibrated probabilities slide
  the operating point toward recall; they do not dominate the uncalibrated arm.
  `always_notify`, which ignores the belief entirely and therefore cannot be moved
  by drift, sits at mean cost 1.7400 with 0 misses, and stays in the report as the
  yardstick any heavily-escalating arm has to be held against.

  The −5 misses does exceed R5's "one or two misses is not evidence" floor, and is
  written as exceeding it *while arriving with a cost increase and a precision
  drop* — an operating-point shift, not a free improvement. This is a finding about
  the fixed cost matrix and the one-step rule, not a defect in the map.

- **Q13 — the published-versus-re-baselined aggregate is unchanged by coincidence,
  and the per-case table is the record.** Both arms report mean cost 1.7200, 8
  missed escalations, and identical action counts, which reads as snapshot
  stability and is not. Six written values moved on test; three crossed a decision
  boundary, and their realised-cost deltas cancel exactly — `a02-deep-017` 0→10,
  `a10-persistent-091` 3→0, `a11-repeated-100` 10→3 — while the action counts
  cancel term for term. The missed-escalation *set* changed even though its size
  did not: drift fixed `a10-persistent-091` and introduced `a02-deep-017`. Had this
  been reported as an aggregate only, the write-up would have carried a false
  stability claim. Cross-snapshot aggregates get a per-case table from here on.

### Open flag carried to Gate 4

One item leaves Gate 2 unresolved on purpose. Nothing is changed now.

**`order_preserved_on_test: false`** — the chosen isotonic map merges distinct
beliefs, so the ordering of calibrated scores on test is not the ordering of the
raw scores. Gate 4's value-of-information ceiling reads the ordering of beliefs and
not only their level, so the ceiling re-run must state which scores it is computed
on and must not assume the merge is harmless. The flag exists because R7 priced
the merge in bits and bits are not what Gate 4 reads. Source:
`results/logprob-elicitation.json` → `analysis.calibration.order_preserved_on_test`.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| Q8 | `digit_expectation` chosen on dev cross-entropy by 0.8071 bits; the metric, not the diagnostic, did the disqualifying. Reverses the earlier Yes/No lean | (AI-proposed) | **changed** |
| Q9 | The collapse diagnostic returned `False` for both; its pooled distinctness count is a documented blind spot — Yes/No collapses on dev alone (8 distinct) — and the §5 thresholds are **not** retuned | (Kaps-decided) | **noted** |
| Q10 | `isotonic` chosen within R7's 0.02-bit margin (0.0747 clear of Platt); `maps_excluded` empty; the merge's cost is `order_preserved_on_test: false` | (AI-proposed) | **confirmed** |
| Q11 | The 11/100 temperature-0 drift is recorded as unreproducible beliefs with an undetermined cause (v1 stored the alias, not the resolved snapshot), noted as L10; the before/after is taken within the fresh beliefs so it isolates the map | (Kaps-decided) | **changed** |
| Q12 | Gate 2's claim is the held-out calibration metrics; the decision metrics are a trade-off — misses 7→2, cost 1.40→1.50, escalations 21→41 of 50 | (Kaps-decided) | **changed** |
| Q13 | The unchanged published→re-baselined aggregate is a coincidence, not stability; cross-date aggregates now carry a per-case table | (AI-proposed) | **noted** |
| — | `order_preserved_on_test: false` carried to Gate 4 as an open flag; nothing changed in Gate 2 | (Kaps-decided) | **noted** |

## Branch and merge policy — changed at the Gate 2 close

The original v2 rule was: all new work goes on `v2`, nothing is committed to
`main`, and `main` sees v2 only once at the end. **That is superseded.** Each gate
now merges to `main` as it closes, after a review pass, and `v2.0.0` is still
tagged only at the very end once the paper compiles and the run reproduces from
cache.

- **M1 — gates merge to `main` one at a time as they finish.** Discussion first,
  then the merge. The original rule was aimed at keeping half-finished work off a
  published repository; merging *reviewed, closed* gates is a different act from
  doing the work on `main`, which is still not done. The reason this is safe to
  start now was verified rather than assumed: v1's published run still reproduces
  from cache byte-for-byte against `results/run.json` (mean 1.72, 16 missed
  escalations), so nothing already published moves when v2 lands.
- **M2 — the first merge carries Gates 0, 1 and 2 together, not Gate 2 alone.**
  Gates 0 and 1 closed before this policy existed and were never merged, so they
  ride along. Splitting them into three retroactive merges would manufacture
  history that did not happen. Gate 3 onward is one merge per gate.
- **M3 — `main`'s two Aug-24 commits (`391f075`, `7573686`) are superseded in
  content, not reverted.** Both edited `decisions/v2-design-decisions.md` directly
  on `main`, which is what the original rule existed to prevent, and they are the
  reason this merge conflicts add/add rather than fast-forwarding. v2's copy is
  taken wholesale: it contains every non-blank line of `main`'s except two headings
  that `main` had indented two spaces — so markdown rendered them as body text
  rather than headings — which v2 had already fixed. Nothing is lost. The commits
  stay in history per the same reasoning as G9/G12.
- **M4 — the 8.8 MB logprob cache goes to `main`.** 99.3% of it is the top-20
  logprob payload, which is what lets a future elicitor be scored with zero new
  calls, and cache-only reproduction is load-bearing for this project. Well inside
  GitHub's limits. Same decision as committing it to `v2`, one step further out.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| M1 | Gates merge to `main` one at a time as they close; supersedes "nothing is committed to `main`"; `v2.0.0` still tagged only at the end | (Kaps-decided) | **changed** |
| M2 | The first merge carries Gates 0–2 together; one merge per gate from Gate 3 on | (AI-proposed) | **confirmed** |
| M3 | `main`'s two Aug-24 design-record commits are superseded in content, not reverted; v2's copy is taken wholesale | (Kaps-decided) | **confirmed** |
| M4 | The 8.8 MB logprob cache lands on `main`; cache-only reproduction is worth the bytes | (Kaps-decided) | **confirmed** |

---

## Resolutions after Gate 3

Gate 3 built the question set, the answer model, the six-vector adapter and the
sweep. Every number here traces to `results/answer-model.json`, written by
`experiments/answer_model.py`; the choices it was held to are in
`decisions/v2-gate3-preregistration.md`, committed with the tables and before the
computation existed.

- **S1 — OQ3's "load-bearing defence" line is wrong, and the correction is
  recorded here rather than by editing OQ3.** OQ3's Gate 1 resolution called the
  likelihood sweep the load-bearing defence of the impossibility result. That was
  written before the answer-model-free ceiling was proved, and it is wrong as
  stated. `VoI(q | b) ≤ V_act(b) − EC(ask | b)` follows from `V_q(b) ≥ 0` alone,
  so the bound grants a free perfect oracle and has already assumed the most
  favourable answer model there is. A sweep over likelihoods cannot defend a bound
  like that — and, the half that matters more, cannot undermine it either. **The
  impossibility needs no defence from Gate 3, and Gate 3 supplies none.** What the
  sweep measures is the stability of the information-gain magnitudes: the
  mechanism, not the claim. OQ3's other half stands unchanged — the VoI honesty
  check is a self-consistency check of the implementation wherever it appears, and
  the absence of external validation stays a Limitations entry. OQ3 itself is left
  as written, per the no-retroactive-edits rule whose build-log form is G9/G12.

- **S2 — the sweep fired its pre-registered fragile branch, and the IG-ordering
  illustration is withdrawn.** Baseline order by mean information gain over the
  100 beliefs: `q_timeline` 0.1290 > `q_authority` 0.1278 > `q_specifics` 0.1040
  bits. Across the 88 variants — 22 free parameters × 4 deltas — the ordering
  flips 27 times, **11 of them at `±0.05`**. That is the second clause of §5
  verbatim, so the illustration is withdrawn rather than repaired by choosing
  better entries; the grid is not changed and the sweep is not re-run on a
  different one.

  Withdrawn: any claim that the information-gain ordering of the three real
  questions means something, and any use of these magnitudes as a stable
  illustration. That narrows what G5 promised. VoI computed case by case under a
  simple documented answer model is still delivered; the *ordering* of questions
  by information gain is not a result this repo carries.

  Not withdrawn, because the sweep does not bear on them: the eight invariants,
  which are properties of the implementation against the Gate 1 §2 definitions and
  hold for any table (0 violations across all 400 question-case pairs); the OQ1
  adapter (S3); `IG(q_null | b) = 0` on all 100 beliefs, the equality case
  asserted rather than argued; and the impossibility result, which is
  answer-model-free. (Kaps-decided: the withdrawal is a result and not a failure —
  the branch fired as designed and stopped an ordering claim the sweep showed was
  an artifact of the entries chosen.)

- **S3 — OQ1 is discharged, and on a coupled posterior that actually arose rather
  than a constructed one.** All 100 priors round-trip `Belief → six-vector →
  Belief` to within `1.11e-16`. `q_specifics` is verified non-separable in exact
  arithmetic and produces a coupled posterior on 96 of the 100 cases; the first,
  `a01-first-001` on answer `concrete` at `P = 0.4488`, makes `narrow()` raise
  instead of projecting onto the marginals. `Belief` is unmodified — its fields
  are still `readiness` and `needs_human`, and the cache format and policy
  signature are untouched, which is what OQ1(b) required. The exact decomposition
  `IG = IG_r + IG_h + I(R ; Hh | U)` holds to under `1e-12` on all 400 pairs, and
  its third term is an independent cross-check on `separates()`: that is a rank-1
  test on the integer table, this is an entropy computed from the posteriors, so
  their agreement is evidence rather than restatement.

- **S4 — a rule written in units it was never checked against is a recurring
  failure mode in this project, not a one-off.** Two instances now, in consecutive
  gates:

  | gate | the rule | units it was written in | the scale it had to resolve |
  | --- | --- | --- | --- |
  | Gate 2 §5 | the collapse diagnostic: fewer than *N* distinct values | a raw count | the `n` it is counted over — pooling dev and test more than doubled Yes/No's count, past the threshold |
  | Gate 3 §5 | the sweep grid: `±0.05` and `±0.10` on a table entry | absolute probability | the 0.0250-bit spread of the mean IGs the sweep had to order, and the size of the entry it lands on — an absolute 0.10 is 14% of a 0.70 entry and 100% of a 0.10 entry |

  The class: **a numeric rule stated in absolute units, governing a quantity whose
  scale the rule never consulted.** Both times the rule fired exactly as written
  and the pre-registration held; both times the blind spot became visible only
  after the data arrived. Neither is retuned, now or then — a threshold edited
  after seeing the data it governs is worth nothing, which Q9 already settled.

  **The check to run before locking any threshold or grid from Gate 4 on:** compute
  the scale of the quantity the rule has to resolve, then either state the rule as
  a fraction of that scale or state explicitly that it is absolute and why. Two
  instances in consecutive gates is a pattern, so it is recorded as a class to
  watch rather than as a second isolated caveat. (The pattern was noticed by
  Claude while diagnosing the flips; recording it as a standing watch item instead
  of another one-off is Kaps-decided.)

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| S1 | OQ3's "load-bearing defence" line is wrong — the impossibility is answer-model-free and needs no defence from Gate 3. Corrected here and in pre-registration §1; OQ3 left as written. OQ3's self-consistency half stands | (AI-proposed) | **changed** |
| S2 | The sweep fired the pre-registered fragile branch — 11 flips of 44 at `±0.05` — so the IG-ordering illustration is withdrawn; the grid is not changed and the sweep is not re-run. Narrows G5 | (Kaps-decided) | **changed** |
| S3 | OQ1 discharged: 100/100 priors round-trip to `1.11e-16`, `narrow()` raises on the real coupled posterior at `a01-first-001`/`q_specifics`/`concrete`, `Belief` unmodified | (AI-proposed) | **confirmed** |
| S4 | A rule written in units it was never checked against is a recurring failure mode — Gate 2's count threshold, Gate 3's absolute sweep grid. Recorded as a class to watch, with a pre-lock check for Gate 4 on; neither rule retuned | (Kaps-decided) | **noted** |

---

## Resolutions after Gate 4

Gate 4 re-ran the answer-model-free ceiling on four belief arms, measured the cost
of three abstention variants on three of them, and landed the figure data path with
a `--check` that re-derives every plotted number. Every number below traces to
`results/voi-ceiling-arms.json`, `results/abstention.json` or
`results/run.json`/`results/logprob-elicitation.json` via
`paper/figures/make_figures.py --check`. The choices the gate was held to are in
`decisions/v2-gate4-preregistration.md`, committed before any of these numbers
existed.

- **U1 — OQ2 resolved as (c): abstention stays a reported diagnostic and the policy
  is untouched.** This is the abstention analogue of the impossibility result. The
  existing minimum-cost policy already handles the "stop and hand off" case
  correctly, so an abstention override is machinery the cost structure provably does
  not need. The diagnostic flag stays — it is useful information for a human
  reviewer — and the override is dropped. That keeps the useful half and discards
  the harmful half.

  The measurement settles it rather than the argument. (a), the `H(b) ≥ τ` override,
  loses at all 33 arm-τ pairs; `beats_baseline_at_any_tau` is `False` on all three
  arms, and the cost of a miss it does avoid runs from 7.5 (published, q=0.7) to
  72.0 (calibrated, q=0.3). (b), the fallback rewrite, is pure cost increase with
  zero miss benefit: +32, +33 and +74 on published, raw and calibrated, with a miss
  delta of exactly 0 on every arm and both splits. Both are worse by construction
  rather than by luck. `escalate_pause` costs strictly more than `escalate_notify`
  in all six labelled states — +3/+2/+2 with `needs_human` false, +2/+1/+1 with it
  true — so any notify→pause rule raises realised cost on every case it touches;
  and `is_escalation` counts both actions, so no such rule can change the miss
  count. There is no operating point where forcing abstention helps.

  The measurement artifact does not carry this resolution. `results/abstention.md`
  §8 records the call as open at the time it was written and states that it does not
  recommend a variant; the decision arrived after the artifact was generated, which
  is the ordering the pre-registration exists to enforce. Retro-fitting it into the
  artifact would erase that ordering, so it lives here.

- **U2 — the calibration floor is the headline result of this gate, and its
  transferable form is the third portable result.** The committed isotonic map
  cannot emit a score below `6/23` = 0.260870, and both thresholds that would let
  `answer` or `ask` fire sit below that floor: `1/5` < `3/13` < `6/23`, all three
  within 0.061 of each other, which is why they are carried as exact rationals — at
  2dp the ordering is invisible. Mechanism: PAVA sets each pooled block's level to
  that block's positive rate, and the lowest block pooled 23 dev cases carrying 6
  positives. All 12 blocks were recovered from the committed knots and the committed
  dev scores without refitting and each level checked against its own
  `positives / n`. `IsotonicMap.predict` interpolates linearly between knots and
  clamps outside them, so the image of ℝ is exactly `[y_first, y_last]` = `[6/23, 1]`.
  The floor is attained by 1 case (`a11-repeated-097`, dev); interpolation lifts the
  other 22 in that block strictly above it. The bound is on the range, not a claim
  about how many cases land on it.

  Transferable form, carried at the same weight as `c_F/ν + c_T/α < 1`: for an
  isotonic map fitted by PAVA, the reachable range is bounded below by the positive
  rate of the lowest pooled block, so a fixed decision threshold beneath that rate
  cannot fire post-calibration however many bits of discrimination the map buys. A
  calibration map has a reachable range and a fixed-threshold policy has thresholds;
  cross-entropy and Brier score never check that the thresholds sit inside the
  range. Featured, not footnoted. (Kaps-decided.)

  What it does not claim is enumerated in `results/voi-ceiling-arms.md` §1 and holds
  here: not that calibration is harmful — the calibrated arm escalates more and
  misses fewer cases needing a human, which is the Gate 2 result and stands; not
  that the map is misfitted — `6/23` is the correct positive rate for that block;
  not that the unconstrained-menu impossibility depends on it; and not that `6/23`
  is a property of isotonic regression in general.

- **U3 — the two kinds of emptiness are not the same kind and are not merged in the
  paper.** For the `calibrated` arm the positive-VoI region is unreachable **by
  construction**: no input can produce a `b_h` below the floor, so the necessary
  condition `b_h < 1/5` fails for every belief the map can emit. For `published`,
  `rebaselined` and `raw` the bound IS reached — 31 raw beliefs meet the necessary
  condition — and the region stays empty only because none of those cases carries
  `no_direct_answer`. That second emptiness is contingent on this dataset; a
  hundred different cases could break it. Structural and contingent emptiness stay
  distinct wherever either appears.

  Alongside it: `b_h < 1/5` is **necessary, not sufficient.** `1/5` is the bound on
  the ray the constrained maximum sits on, so it is the most favourable direction in
  the simplex; a belief below it must also carry `no_direct_answer` and lie near
  that ray. The sufficient test is the per-case ceiling with constraints applied,
  which is reported per arm and is negative on all 400 case-arm pairs. The binding
  wording rule stands unchanged: asking is never rational **on the unconstrained
  action menu**, with the constrained-menu positive region and its emptiness in this
  dataset stated explicitly.

- **U4 — the arms re-run confirms an analytic fact and is written up as confirming
  one.** `V_act(b) ≤ min(α·b_h, ν·(1−b_h))` for every belief and `EC(ask | b)` is
  flat in readiness, so `max_b [V_act(b) − EC(ask | b)]` is a function of the cost
  matrix alone: `−2/13` = −0.153846. On the unconstrained menu, "the impossibility
  survives recalibration" is therefore analytic, not an empirical finding, and
  `results/voi-ceiling-arms.md` §2 says so in the artifact rather than only in the
  paper. Checked rather than assumed: the seven belief-independent sections are
  identical across all four arms by exact equality of `json.dumps(section,
  sort_keys=True)`, and the script refuses to report a contrast if they ever differ.
  The only part of §2 an arm can change is whether a real case reaches the positive
  region the constrained menu opens up, and none does.

  §4's regression guards reproduce counts `results/rebaseline.json` already commits,
  including the calibrated arm's zero `answer` decisions on test. The artifact states
  that this shows the arm loader rebuilds the same beliefs and does not discover
  them. The falsifier against dressing committed data as a finding stands.

- **U5 — S4's pre-lock check ran, and it found a second failure mode underneath the
  first.** τ was locked as deciles of the observed `H(b)` distribution on the arm
  being scored, with both the quantile and the absolute bit value reported per arm
  and cross-arm incomparability in absolute bits declared. The scale check is what
  made this necessary: the observed distribution is bunched (published spans
  0.000000–2.456426 bits with 8 distinct values), so an absolute grid over the
  0–2.585 bit theoretical range would have put most of its points where almost no
  cases live. Deciles make the step commensurate with the quantity by construction.

  Underneath it: `H(b)` values that are mathematically equal differ in the last
  bits, by up to 8.88e-16, so two identical published deciles read as different
  thresholds and fired on 49 cases and 44. `H(b)` is now quantised to 12 decimals
  before any comparison against τ, which collapses exactly 5 spurious distinctions
  on published (24 → 19) and none on raw or calibrated. The guard is non-circular
  by construction: the noise bound is derived independently as
  `8 · math.ulp(max|H|)` = 3.55e-15, the tolerance 1e-12 is asserted to sit strictly
  between that bound and the smallest genuine gap per arm (9.99e-03 published,
  3.92e-05 raw, 4.97e-06 calibrated), and gaps are classified by the noise bound
  rather than by the tolerance. Both ends carry negative controls — `H_DECIMALS = 2`
  is refused for crossing the signal, `H_DECIMALS = 17` for sitting below the noise.
  Without the tolerance guard the artifact would have shipped two wrong firing
  counts. (Found by Claude while checking why two equal deciles disagreed; the
  requirement that the guard not be circular is Kaps-decided.)

- **U6 — the safest-first tie-break changes one action, on dev, on one arm.**
  `a11-repeated-097` is `answer` under v1's legacy rule and `hold` under
  safest-first. The test split — which is the split every committed score this
  artifact checks itself against is taken on — is insensitive on all three arms, 0
  actions differing. Where the two rules differ on dev, `results/abstention.md`
  reports the fresh rule and `results/run.json` reports the legacy one, and the
  artifact says so. Nothing is changed: the sensitivity is dev-only and dev is
  labelled in-sample throughout.

- **U7 — two lines of `paper/main.tex` state a value claim with a threshold
  bracket, and the correction is deferred to the paper gate rather than made
  here.** The shaded band on the calibration figure carries two claims with two
  different brackets, and they were conflated:

  | claim | interval | bracket | why |
  | --- | --- | --- | --- |
  | no case takes a value strictly inside | `(0.2, 0.3)` | open at both ends | 17 of the 100 cases take exactly 0.3 |
  | every threshold decides as `3/13` does | `(0.2, 0.3]` | half-open | the rule is `answer iff b_h < t`, so a threshold at 0.3 leaves those 17 cases on the escalate side exactly as `3/13` does |

  `paper/main.tex:499` ("none of them falls in $(0.2, 0.3]$") and
  `paper/main.tex:728` (the figure caption, "no case falls in $(0.2, 0.3]$") are
  both value claims carrying the threshold bracket, and both are false as written.
  `paper/main.tex:971` is a threshold claim and its bracket is correct, though
  "any other value" would read better as "any other threshold". Line 499 draws the
  correct threshold conclusion from the false value premise in the same sentence, so
  the fix is to split the two rather than to change a bracket.

  `paper/figures/make_figures.py` is fixed now: `empty_value_interval` and
  `equivalent_threshold_interval` are separate fields with separate `closed`
  strings, the render legend carries both brackets, and the threshold claim is
  verified as a partition identity — `partition(3/13) == partition(0.3)` is True,
  `== partition(0.2)` and `== partition(0.4)` are False — rather than inferred from
  the emptiness of the value gap. `--check` found this on its first run against the
  committed artifacts, which is the whole reason §8 required it. The `.tex` edits
  are deferred so that the paper gate changes prose once, deliberately, rather than
  having a figure script edit the manuscript as a side effect.

- **U8 — pre-registration §8's "two bin schemes" is loose, and the correction is
  recorded here rather than by editing §8.** There is one bin scheme: ten
  equal-width bins with the same index rule, `min(⌊10p⌋, 9)`, on all three panels.
  v1's panel occupies 8 of the 10 because the elicited marginal took only 8 distinct
  one-decimal values, and `experiments/run_policies.py` drops the empties before
  writing them; `src.calibrate.reliability_bins` keeps them, so the Gate 2 tables
  carry all 10 with `n: 0`. What actually differs across the panels is the
  population (100 cases against 50), the score source, and whether empty bins
  survive to the artifact — not the bin width. §8's conclusion is unchanged and
  still correct for those reasons: the panels are not drawn on one axis. §8's own
  bracket on v1's shaded region, `(0.2, 0.3)`, was right; it is `main.tex` that
  drifted. §8 is left as written, per the no-retroactive-edits rule at G9/G12.

- **U9 — Q5 landed as the data path plus `--check`; rendering is still deferred.**
  `figure_data()` now returns three panels — `v1_needs_human`, `gate2_test_raw`,
  `gate2_test_calibrated` — plus the reason they are not one figure. `check()`
  re-derives every plotted number from the per-case records: the v1 bins from the
  100 elicited marginals in `results/run.json`, both Gate 2 panels from the 50 test
  scores in `analysis.recalibrated_scores` joined to labels in `run.json`, then ECE,
  cross-entropy in bits, Brier and base rate to 1e-12, and the `6/23` floor with the
  assertion that no test score falls below it. `_bin_index` and `_ece` are restated
  in the module rather than imported from `src.calibrate`, which is what wrote the
  committed tables — re-deriving a number with the function that produced it checks
  nothing. Panels 2 and 3 declare `renders: false` and name the paper gate. The
  test file's negative controls doctor the committed payloads and assert each check
  family fires; the derived shaded band is tested on a deliberately stale
  panel-versus-records pair, because within one payload the band and the check move
  together and cannot disagree.

- **U10 — the `order_preserved_on_test: false` flag carried from Gate 2 is
  discharged, and it overstated the risk.** Gate 2 parked it because "Gate 4's
  value-of-information ceiling reads the ordering of beliefs and not only their
  level, so the ceiling re-run must state which scores it is computed on and must not
  assume the merge is harmless." Two things settle it. Isotonic regression is weakly
  monotone, so it cannot invert a pair, only send both members to the same value:
  the knot y-values are non-decreasing, and on test there are **0 inversions and 16
  merged pairs** at full precision, 31 at the pre-registered 3dp. And the ceiling is
  pointwise in the belief — `EC(ask | b) = 2 + 2·b_h`, and `V_act` is a minimum over
  actions at that same belief — so it reads levels, not ranks. Ties therefore cannot
  move it in any direction the per-arm tables do not already show. The flag's
  procedural half is honoured regardless: every arm states which scores it is
  computed on, and the four arms are reported separately rather than pooled.

The suite is **654 passing** at this gate's close, from 510 at its open.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| U1 | OQ2 resolved as (c): the diagnostic flag stays, the override is dropped. The abstention analogue of the impossibility result — the minimum-cost policy already handles hand-off correctly. (a) loses at all 33 arm-τ pairs, (b) costs +32/+33/+74 for a miss delta of 0 | (Kaps-decided) | **changed** |
| U2 | The calibration floor is the gate's headline and its transferable form is the third portable result, at the same weight as `c_F/ν + c_T/α < 1`. `1/5 < 3/13 < 6/23`; the lowest PAVA block pooled 23 dev cases with 6 positives | (Kaps-decided) | **confirmed** |
| U3 | Structural emptiness (calibrated, by construction) and contingent emptiness (published/rebaselined/raw, this dataset) stay distinct; `b_h < 1/5` is necessary not sufficient, and the sufficient test is negative on all 400 case-arm pairs | (Kaps-decided) | **confirmed** |
| U4 | The unconstrained-menu impossibility is analytic and the artifact says so; the seven belief-independent sections are checked identical across arms by exact equality; §4's guards reproduce committed counts and do not discover them | (AI-proposed) | **confirmed** |
| U5 | τ locked as deciles of the observed `H(b)` distribution per arm, discharging S4's pre-lock check; `H(b)` quantised to 12 decimals with a non-circular tolerance guard, which corrected two wrong firing counts | (AI-proposed) | **changed** |
| U6 | The safest-first tie-break differs from v1's legacy rule on exactly one case, `a11-repeated-097`, on dev only; the test split is insensitive on all three arms and nothing is changed | (AI-proposed) | **noted** |
| U7 | `paper/main.tex:499` and `:728` state a value claim with the threshold bracket and are false as written; `:971` is correct. Fixed in `make_figures.py` now, deferred in the `.tex` to the paper gate | (AI-proposed) | **noted** |
| U8 | Pre-registration §8's "two bin schemes" is loose — one scheme, differing populations, score sources and empty-bin retention. §8's conclusion and its own bracket stand; §8 left as written | (AI-proposed) | **noted** |
| U9 | Q5 lands the three-panel data path and a `--check` that re-derives every plotted number from the per-case records; rendering stays deferred to the paper gate | (Kaps-decided) | **confirmed** |
| U10 | Gate 2's `order_preserved_on_test: false` flag is discharged: isotonic is weakly monotone, so 0 inversions and 16 merged pairs on test, and the ceiling is pointwise in the belief. The flag overstated the risk | (AI-proposed) | **changed** |

---

## Merge policy and paper debts — recorded at the Gate 4 close

A review pass before Gate 5, over the four closed gates rather than any new work.
Nothing here changes a number; M5 reverses a policy and V1–V3 name three defects
in `paper/main.tex` that the paper gate has to fix.

- **M5 — everything stays on `v2`; one merge to `main` at the very end.**
  Supersedes M1 and M2. The per-gate merge policy was aimed at keeping `main`
  current, and with a single person on the branch there is nothing for it to be
  current *for*. The three-gate backlog — Gates 0–2, 3 and 4, 26 commits — stays
  on `v2`, pushed, so nothing is at risk from not merging. `v2.0.0` is tagged at
  Gate 8 as it always was, after `v1.0.0`, and the merge happens once behind it.
  What M1
  verified stays verified and is not re-verified: v1's published run still
  reproduces from cache byte-for-byte, so nothing published moves when v2 lands.
  M3 and M4 are unaffected — they describe what the merge carries, not when it
  happens.

- **V1 — `reliability-needs-human.pdf` has never existed in the repository.**
  `git log --all --diff-filter=A -- '*reliability*'` returns nothing on any branch,
  yet `paper/main.tex:719` includes it and the tracked `paper/main.pdf` embeds it:
  three Form XObjects and the filename present in the PDF body. It was built from a
  local, untracked file at a time when the root `figures/*` rule was still ignoring
  it. The consequence is that the published artifact carries a figure that cannot be
  rebuilt from a fresh clone. Q4 removed the `.gitignore` obstacle and Q5 recorded
  that the figure "will be committable the moment it exists" — it still does not
  exist, and `render()` in `paper/figures/make_figures.py` has never been executed
  because matplotlib is absent from the environment. Gate 7 owes all three panels
  and the first commit of panel 1's PDF.

- **V2 — `paper/main.tex:683` is false in its mechanism, not only its wording.**
  It reads that `ask` "is dominated at both ends and can only win in a narrow middle
  band that the quantized beliefs never land in." There is no such band on the
  unconstrained menu: the maximum of `V_act(b) - EC(ask|b)` over the whole simplex
  is `-2/13`, so no belief anywhere makes asking pay. Quantization is also not the
  cause of the emptiness — the raw arm carries 100 distinct beliefs and the region
  stays empty. This is a heavier correction than U7's brackets, and it is also where
  the theorem belongs: the sentence is already reaching for it. The replacement must
  keep the binding wording — never rational **on the unconstrained action menu**,
  with the constrained-menu region `b_h < 1/5` and its emptiness here stated.

- **V3 — "the floor" names two different objects and they need separating before
  either is written up.** `main.tex:1045` reads "The floor is therefore set by the
  granularity of the elicitation, not by the calibration method," about v1's
  in-sample survivors at `b_h = 0.20`. Gate 4's floor is `6/23` and is set precisely
  *by* the calibration method — it is the lowest PAVA block's positive rate. Both
  claims are true of different objects, a belief's granularity and a map's reachable
  range, and neither needs correcting on its own. Together in one paper under one
  word they read as a contradiction. Naming them apart is a Gate 7 obligation, not
  an optional clarification.

- **The Gate 8 open-item paragraph at the head of this file is already
  superseded in place.** The G-series paragraph states that what remains genuinely
  open at Gate 8 is the `.gitignore` conflict. Q4 fixed it during Gate 2a and the
  build-log records it pulled forward; `.gitignore` lines 34 and 42 confirm it. The
  paragraph is left as written, per the G9/G12 rule and the S1/U8 precedent, and
  this line is the correction. The only Gate 8 items now are the two tags and the
  single merge.

- **V4 — Gate 7 gets a pre-registration, the same instrument Gates 2, 3 and 4
  had.** Each of those pre-registrations caught something the gate would otherwise
  have discovered too late: the collapse threshold's scale, the sweep grid's
  absolute units, the τ grid's. Gate 7 folds four gates of results into 1102 lines
  of existing prose containing three known-false claims, and prose has no test
  suite, so it is the gate with the least grip and the most to get wrong. The
  pre-registration fixes three things before any `.tex` is edited: which v2 result
  lands in which section, which v1 sentences are **replaced** rather than extended,
  and which number in the paper traces to which artifact.

- **V5 — matplotlib is permitted, scoped as a figures-only dependency.** The
  promise that matters is that the results reproduce with no dependencies:
  `src/`, the cache-only belief path, the ceiling and the calibration fit stay
  pure-stdlib, and none of them may import it. Rendering is not part of that path.
  `make_figures.py --check` re-derives every plotted number in pure stdlib, so the
  verification that a figure is honest survives in an environment that cannot draw
  it — which is the environment the test suite runs in. Stated the other way round:
  results reproduce with zero dependencies; figures need exactly one, declared.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| M5 | Everything stays on `v2`; a single merge to `main` at the very end, `v2.0.0` tagged at Gate 8 behind `v1.0.0`. Supersedes M1 and M2; M3 and M4 stand | (Kaps-decided) | **changed** |
| V1 | `reliability-needs-human.pdf` was never committed on any branch, so the tracked `main.pdf` embeds a figure no clone can rebuild; `render()` has never run. Gate 7 owes three panels and the first PDF commit | (AI-proposed) | **noted** |
| V2 | `paper/main.tex:683` attributes `ask`'s emptiness to a narrow band the quantized beliefs miss; there is no such band on the unconstrained menu and the raw arm's 100 distinct beliefs leave it empty too. Gate 7 replaces it with the theorem, keeping the binding wording | (AI-proposed) | **noted** |
| V3 | "The floor" means belief granularity at `main.tex:1045` and the map's reachable range in Gate 4; both true, contradictory under one word. Gate 7 names them apart | (AI-proposed) | **noted** |
| V4 | Gate 7 gets a pre-registration: which result lands in which section, which v1 sentences are replaced rather than extended, which number traces to which artifact | (Kaps-decided) | **confirmed** |
| V5 | matplotlib is a figures-only dependency; the results-reproduction path stays dependency-free and `--check` is the stdlib verification that survives without it | (Kaps-decided) | **confirmed** |
| — | The G-series Gate 8 open-item paragraph is superseded by Q4 and left unedited; Gate 8's remaining items are the two tags and the merge | (AI-proposed) | **noted** |

## Resolutions after Gate 5

Gate 5 computed per-case VoI for the first time — the whole `V_q` term, not just the
analytic bound — and priced the entropy-threshold ask baseline on four belief arms
over the pre-registered decile grid. Every number below traces to
`results/entropy-baseline.json`, checked against `results/voi-ceiling-arms.json`,
`results/rebaseline.json` and `results/run.json`. The choices the gate was held to
are in `decisions/v2-gate5-preregistration.md`, committed before any of these
numbers existed. Four of the five entries here are things that pre-registration did
not anticipate, and one of them corrects it.

- **X1 — a cost-side adapter was needed, because `narrow` refuses coupled
  posteriors.** The pre-registration assumed `costs.expected_cost` would price the
  posteriors. It cannot: it takes a factorised `Belief`, and `q_specifics` produces
  posteriors that do not factorise — the committed example is `a01-first-001` on
  answer `"concrete"` at `p_u = 0.4488`. `narrow` raises `NonFactorisingError`
  rather than projecting onto marginals, by an earlier decision made to keep the
  coupling visible, so there was no legitimate way to turn those posteriors into
  something `expected_cost` accepts. `ec_joint(action, joint)` prices the joint
  directly and is asserted to agree with `costs.expected_cost` on all 500
  (prior, action) pairs, max delta 0. One cost matrix, two callers, agreement
  checked rather than assumed. The test that matters is not that the adapter agrees
  — it is that `narrow` still raises on the committed coupled case, because the day
  it starts projecting silently, the adapter becomes dead weight hiding the
  coupling.

- **X2 — invariant 6 is not the independent cross-check the pre-registration called
  it.** Substituting the definition of VoI into invariant 6 cancels `V_act` and
  `EC(ask)` and leaves `V_q ≥ 0`, which holds for free because every entry of
  `costs.COST` is non-negative. This is measured, not argued: the invariant's slack
  equals `V_q` to within 7.77e-16 on all four arms. So the pre-registration, and the
  instruction to report "invariant 6's result" as the cross-check that mattered
  most, both overrated it. It passes, and its passing is worth close to nothing.

  The independent check is `ceiling_agreement`, and it is exact. Recomputing
  `EC(ask | b) − V_act(b)` from the beliefs and comparing to the committed per-case
  ceiling gives `max_ceiling_delta = 0.0` on all four arms — bit-identical, because
  `widen` mirrors `state_probability` and `STATES` iterates in the order
  `expected_cost` sums in. Two further routes agree: `EC(ask | b)` against the exact
  `2 + 2·b_h` of invariant 5 to 8.9e-16, and `V_act` recovered as
  `ceiling + EC(ask | b)` to 2.2e-16. Non-positive tier-1 excesses: 0 of 400 on
  every arm. Invariants 2, 3 and 4 hold on all 400 pairs per arm, invariant 4 with
  exact residuals and a constant-argmin count of 234 / 235 / 236 / 253 that is
  reported, not predicted.

- **X3 — the committed bound is attained, not merely respected.** `V_q = 0` exactly
  on 16 published, 12 rebaselined, 0 raw and 52 calibrated case-question pairs. On
  those pairs a free, perfect oracle drives post-answer expected cost to zero and
  asking still loses by the full `−ceiling`. That closes off the reading that the
  ceiling is negative only because it is slack: on a quarter of the calibrated pairs
  there is no slack to be had. Raw has none because its beliefs are continuous,
  which is why the finding is stated per arm.

- **X4 — each arm is scored against its own v1 total, not against published's 86.**
  v1's policy replayed on rebuilt beliefs scores 86 on published, 86 on rebaselined,
  70 on raw and 75 on calibrated, all four committed in Gate 2. The first version of
  the render printed 86 as the reference line under every arm's table while the
  excess column was computed against the arm's own total, so raw's `+7.70` at the
  0.9 decile was labelled against a total raw never had. The reference is now the
  arm's own, and it is checked: the top of every grid fires on nothing, so that row
  has to reproduce the arm's committed Gate 2 score, and it raises if it does not.
  This is S4's shape again in a new place — a number stated against a reference the
  statement never consulted.

- **X5 — the realised column is not monotone in τ, and the exception is worth
  keeping.** The expected tiers must fall as τ rises: the firing sets are nested and
  every firing case contributes a positive excess. Both are asserted. The realised
  column has no such guarantee, and on the rebaselined arm it inverts once — the
  firing count falls 12 to 11 between the 0.7 and 0.8 deciles and the realised total
  rises 109.60 to 113.60. The cause is one case, `a02-deep-017`: v1 answers it and
  eats a realised 10, where ask-then-act realised 6, so dropping it from the firing
  set costs 4. Its expected tier-1 excess is `+0.40` throughout. Asking was expected
  to lose on that case and did in fact win it. Nothing rests on this — it sits on the
  arm that carries no claim — but it is the cleanest illustration in the repo that
  the impossibility result constrains expected cost and says nothing about a single
  realised draw, so it is recorded with its cause rather than smoothed away.

- **X6 — the attainment result goes in the theorem section, as a second beat
  sharpening the main claim.** Not a separate finding and not artifact-only. The
  order is: asking is never rational on the unconstrained action menu, and then — on
  16 published and 52 calibrated case-question pairs — the ceiling is attained, so
  asking loses by the full margin even against perfect information. The second
  sentence amplifies the first rather than qualifying it, which is why it sits
  immediately after the theorem instead of in a results table.

- **X7 — the realised inversion is written as a mechanism illustration off the
  case, not off the arm.** `a02-deep-017` is the example: a case where asking was
  expected to lose and realised a win. One or two sentences in failure analysis or
  discussion, drawn from the case and its two realised costs — v1 answers for 10,
  ask-then-act realises 6, expected tier-1 excess `+0.40` throughout. The
  rebaselined arm's totals stay out of the paper: the 12-to-11 firing count and the
  109.60-to-113.60 rise are how the case was found, not the claim, and that arm
  carries no claim. Framing it off the case keeps the illustration and leaves the
  no-claim lock intact.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| X1 | `ec_joint` prices coupled posteriors because `narrow` raises rather than projecting; agreement with `costs.expected_cost` checked on all 500 (prior, action) pairs, max delta 0. The pre-registration did not anticipate a cost-side adapter | (AI-proposed) | **changed** |
| X2 | Invariant 6 reduces algebraically to `V_q ≥ 0` — slack equals `V_q` to 7.77e-16 — and is not independent evidence for the bound. `ceiling_agreement` is, at `max_ceiling_delta = 0.0` exactly on all four arms | (AI-proposed) | **changed** |
| X3 | The bound is attained: `V_q = 0` on 16 / 12 / 0 / 52 pairs, so the ceiling's negativity cannot be attributed to slack. Raw has none because its beliefs are continuous | (AI-proposed) | **noted** |
| X4 | Each arm's excess is measured against its own committed v1 total — 86 / 86 / 70 / 75 — not published's 86; the τ top-of-grid row is checked against `rebaseline.json` per arm | (AI-proposed) | **changed** |
| X5 | The realised column inverts once, on the no-claim arm: `a02-deep-017` leaves the firing set, v1 answers it for 10 where ask-then-act realised 6. Expected excess `+0.40`. Recorded with its cause | (AI-proposed) | **noted** |
| X6 | The attainment result lands in the theorem section as a second beat — "asking never wins on the unconstrained menu" then "and on N pairs the ceiling is attained, so it loses by the full margin even against perfect information." A sharpening, not a separate finding | (Kaps-decided) | **confirmed** |
| X7 | The realised inversion is written as a mechanism illustration drawn from `a02-deep-017`, in failure analysis or discussion, framed off the case and not off the rebaselined arm's totals | (Kaps-decided) | **confirmed** |

## Resolutions after Gate 6

Gate 6 wrote no code. It states the one-question-lookahead boundary the definitions
carried forward, and proves that the impossibility result does not depend on it.
Everything below traces to `decisions/v2-policy-boundary.md`, whose numbers come from
`results/voi-ceiling.json` and `results/entropy-baseline.json` and were all committed
in earlier gates. This is the one gate with no pre-registration, because there is
nothing to pre-register: no quantity is computed, so there is no result to be tempted
by after the fact.

- **Y1 — the shipped policy is `W_1` in a family that is now written down.** With
  `W_0(b) = V_act(b)` and
  `W_k(b) = min{ V_act(b), EC(ask | b) + Σ_u P_b(u)·W_{k−1}(b^u) }`, the analysis
  priced in Gate 5 is exactly `W_1`, because `V_q(b) = Σ_u P_b(u)·V_act(b^u)` uses
  `W_0` as its continuation. Naming that inner term is the whole of what fixes the
  depth at one; nothing else in the definition of VoI sets a depth. The budget counts
  questions, not turns.

- **Y2 — `V(b^u)` in place of `V_act(b^u)` is wrong twice, and neither error is
  depth.** First, `ask` is in the menu, so `V(b^u) ≤ EC(ask | b^u)` identically — the
  same tautology recorded at `v2-definitions.md:129`, moved one level down and hidden
  rather than fixed. Second, the object is not `W_2`: `W_2` charges the second question
  a continuation, `V(b^u)` does not, and the gap is exactly the missing
  `Σ_{u'} P_{b^u}(u')·W_0(b^{u,u'}) ≥ 0`. So it implements a policy that believes the
  second question's follow-up is free. The under-pricing sits entirely on the ask
  branch, which biases the comparison in favour of the action under test — the one
  place the analysis cannot afford a thumb on the scale. The file carries the
  instruction not to call it "two-step," because that name makes a rigged test sound
  like an upgrade.

- **Y3 — depth-independence: the theorem is now proven for every depth, not asserted
  from `k = 1`.** Two premises, both already committed. Premise A, the ceiling
  `V_act(b) − EC(ask | b) ≤ −2/13`, is a maximum over *all* beliefs — the whole
  readiness simplex crossed with `b_h ∈ [0,1]`, exact in `Fraction`, attained at the
  all-hot vertex with `b_h = 3/13`, cross-checked by a 60-step grid reaching `−0.1667`
  — so it binds at every node of any lookahead tree, since posteriors are beliefs.
  Premise B is `W_k ≥ 0`, from the non-negativity of `costs.COST`. Then for every
  `k ≥ 1` the ask branch is `≥ EC(ask | b) ≥ V_act(b) + 2/13 > V_act(b)`, so
  `W_k = V_act` and the tree collapses to acting now.

  Premise B is invariant 6, and this is where X2's correction earns its keep. What made
  invariant 6 worthless as an independent check — that it follows from the matrix alone,
  with no reference to the data, the answer model, the question set or the depth — is
  precisely what makes it the only kind of premise assertible at every node of a tree
  nobody enumerates. A data-dependent check would have to be verified per node and
  could not be quantified over. It is load-bearing *because* it is trivial. This
  upgrades `v2-definitions.md:259` from a claim to a result, and splits v1's myopia
  framing: "a strict one-step rule does not price asking" stays true and stays a named
  limitation, while "asking is undervalued and would earn its place if priced" is false
  on this matrix and menu, at every depth.

- **Y4 — the four scope limits are kept exactly as written, including the last
  restraint.** The constrained menu, where `no_direct_answer` lifts the ceiling to
  `+1.0` and premise A fails, with the region's emptiness structural for `calibrated`
  (the isotonic range starts at `6/23`, above `1/5`) and contingent for the other three
  arms. A cheaper question, since premise A is a statement about the `(2, 4)` row and
  `λ = 15/16` flips it. Deferral, which no row of `costs.COST` prices, leaving v1's
  turn-boundary limitation untouched. And the scope of the claim itself: this bounds the
  value of one more question inside a deeper policy, not every interaction design. The
  claim must not be allowed to drift into "no interaction design could justify asking."

- **Y5 — the boundary owes the paper two edits, both in Gate 7.** A third beat in the
  theorem section, after the theorem and X6's attainment sharpening, saying the margin
  does not close at any lookahead depth because the bound needs only non-negative
  continuation costs. And the retraction of the myopia framing in Limitations, where v1
  made the claim — `main.tex:249`, `:343`, `:687`, `:947`, `:1050`. `:687` sits inside
  the `:683` band-claim debt (V2), so Gate 7 rewrites that line once, not twice.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| Y1 | The shipped policy is `W_1` in the family `W_k(b) = min{ V_act(b), EC(ask \| b) + Σ_u P_b(u)·W_{k−1}(b^u) }`; `V_q`'s inner `V_act(b^u) = W_0(b^u)` is what fixes the depth at one, and the budget counts questions, not turns | (AI-proposed) | **noted** |
| Y2 | `V(b^u)` is wrong twice — it re-prices `ask` terminally one level down, and it is not `W_2` but a policy that believes the second question's follow-up is free, biasing the comparison toward the action under test. Not to be called "two-step" | (AI-proposed) | **noted** |
| Y3 | Depth-independence is proven, not asserted: the simplex-wide ceiling plus `W_k ≥ 0` give an ask branch `≥ V_act(b) + 2/13` at every node and every depth. Invariant 6 is load-bearing because it is trivial. `v2-definitions.md:259` becomes a result, and v1's myopia claim splits | (AI-proposed) | **changed** |
| Y4 | The four scope limits stay exactly as written — the constrained menu, a cheaper question, deferral, and the restraint that this bounds one more question inside a deeper policy rather than every interaction design | (Kaps-decided) | **confirmed** |
| Y5 | Two paper edits in Gate 7: a theorem-section third beat on depth, and the myopia retraction in Limitations where v1 made it (`main.tex:249`, `:343`, `:687`, `:947`, `:1050`), with `:687` handled once under V2's `:683` | (Kaps-decided) | **confirmed** |

## The float-reproduction fix — two undeclared tie-breaks and a Python floor

- **AB1 — the five failing tests are a CPython version change, not an operating-system
  difference.** CPython 3.12 made `sum()` over floats use Neumaier compensated
  summation. Verified by running the whole suite under 3.11, 3.12, 3.13 and 3.14:
  3.12 and later reproduce `results/entropy-baseline.json` byte for byte, 3.11 does
  not. The disagreement is 826 leaves, of which 818 are floats differing by at most
  1.110e-15. Two earlier hypotheses — macOS versus Linux `libm` for `log2`, and
  hash-order nondeterminism — were tested and disproved rather than left standing.
  The remaining 8 leaves are discrete and survive any tolerance, which is what turned
  a float-noise report into two defects.

- **AB2 — the comparator forgives a float-versus-float leaf within 1e-9 and nothing
  else.** `tests/reproduction.py` runs two independent comparisons of the fresh render
  against the committed file: a walk over the parsed structure, and a line-by-line text
  comparison. Each catches what the other cannot — the walk sees `100` becoming `100.0`
  and a reordered key, the text comparison sees a changed indent and a missing trailing
  newline. Every `Fraction` is rendered as a string and so is not a float leaf: the
  exactness claims the artifacts carry (`ceiling_exact`, `t_star`, `max_v_act`) still
  compare character for character, as do all counts, ids, bools, nulls, list lengths
  and the key order itself. Each of those has its own negative control in
  `tests/test_reproduction.py`. Only `entropy-baseline.json` and `voi-ceiling*.json`
  move to the tolerance; every other committed artifact, including
  `entropy-baseline.md`, stays byte for byte.

- **AB3 — the oracle's `argmax_q VoI` tie-break is declared.** On some cases the three
  real questions come out at exactly equal VoI, and `max()` resolved the tie by the
  last bit of a float sum — so the oracle's pick, and the agreement count computed from
  it, moved with the interpreter. This is the S4 failure mode a fourth time: a rule
  selecting on a quantity whose tie structure the rule never consulted. `ARGMAX_DECIMALS
  = 12` now rounds before comparing and `ARGMAX_TIE_BREAK` names the resolution
  (declaration order in `QUESTIONS`). The tied set is recorded per case, because
  `by_question` is stripped from the JSON and the tied set would otherwise be the one
  fact about the tie that nothing keeps.

- **AB4 — the grid crosscheck reports a plateau, not a witness.** `grid_crosscheck`
  returned one point as *the* argmax. 1185 of the 115351 points at `n = 60` attain the
  maximum to 12 decimals, so the claim was slightly false before it became unstable —
  which point got reported was decided by the same last bit. It now reports
  `n_grid_points_attaining_the_max`, `grid_points_searched`, `grid_argmax_is_unique:
  false`, and a declared `GRID_TIE_BREAK` (lowest `(hot, warm, b_h)`). The reported
  point moves from `hot 0.2667, warm 0.7` to `hot 0.1333, warm 0.8333`; both are on the
  plateau, and no file cites the point.

- **AB5 — residuals print `0` or `~0`, never three significant figures of summation
  order.** `-2.22e-16` in an invariant table reads as a measurement to three digits
  when it is the order the terms were added in. `_resid` prints exact zero as `0`,
  anything below the 1e-12 tolerance as `~0`, and a real value in full, with
  `RESIDUAL_LEGEND` printed under the table. Exact `0` is preserved as its own symbol
  because X2's "recomputed and committed ceilings agree to the last bit" claim is the
  difference between an exactly-zero residual and a below-tolerance one. A magnitude
  bound like `< 1e-12` was rejected: `invariant_2_min_slack` is signed, and a bound
  drops the sign.

- **AB6 — the Python floor is 3.12, declared in one place and asserted against three.**
  A reproducibility claim that silently depends on the interpreter is the same class of
  gap as v1's unrecorded model id (L10): the artifact was produced under conditions the
  artifact does not record. Two committed claims genuinely need ≥ 3.12 —
  `ceiling_agreement.max_ceiling_delta == 0.0` exactly on all four arms, and
  `entropy-baseline.md`'s `0`-versus-`~0` cells — so the floor is real, not cosmetic.
  `MIN_PYTHON` in `tests/reproduction.py` is the single declaration; `WHY_MIN_PYTHON`
  carries the reason; and three tests pin it to the CI matrix, to the README, and to
  the running interpreter, so none of the three can drift alone. A fourth asserts the
  matrix runs the floor itself, since a floor no leg tests is a claim nothing checks.
  The matrix moves from `["3.10", "3.12"]` to `["3.12", "3.13", "3.14"]`; the 3.10 leg
  it replaces could not pass.

- **AB7 — correction: the agreement count does not move.** I reported it as 29 → 30 in
  published and 26 → 27 in raw. Under the declared tie-break both interpreters produce
  29 and 26, which are the committed values, so the requirement that the change touch
  no paper line or decision file is satisfied because there is no change. What the
  declared tie-break does expose is new and material: the oracle's pick needed the
  tie-break on 13 of 50 test cases on published and 12 of 50 on raw. On a tied case,
  agreement with argmax-IG is an artifact of the tie-break rather than evidence that
  the two rules select alike, so "agrees on 29 of 50" is now reported next to the tie
  count in both the JSON and the markdown, and neither number may be quoted alone.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| AB1 | The five failures are CPython 3.12's compensated `sum()`, not an OS difference; 818 of 826 differing leaves are floats within 1.110e-15, and the surviving 8 are discrete. The `libm` and hash-order hypotheses were disproved | (AI-proposed) | **changed** |
| AB2 | `tests/reproduction.py` forgives only a float-versus-float leaf within 1e-9, running a parsed walk and a line comparison because each catches what the other cannot. `Fraction` strings, counts, ids, bools, nulls, lengths and key order stay exact; only the three JSON artifacts move off byte comparison | (AI-proposed) | **confirmed** |
| AB3 | The oracle's `argmax_q VoI` tie-break is declared — rounding at 12 decimals, then declaration order in `QUESTIONS` — and the tied set is recorded per case. S4 a fourth time | (Kaps-decided) | **changed** |
| AB4 | The grid crosscheck reports the 1185-point plateau, the 115351 points searched, `grid_argmax_is_unique: false` and a declared lowest-`(hot, warm, b_h)` tie-break, instead of a witness that was never unique | (Kaps-decided) | **changed** |
| AB5 | Residuals render as `0` (exactly zero) or `~0` (below the 1e-12 tolerance) with a printed legend, never as three significant figures of summation order. A magnitude bound was rejected because `invariant_2_min_slack` is signed | (AI-proposed) | **confirmed** |
| AB6 | The floor is Python 3.12, declared once as `MIN_PYTHON` and asserted against the CI matrix, the README and the running interpreter, with a fourth test requiring the matrix to run the floor. An interpreter-dependent reproducibility claim is an L10-class gap | (Kaps-decided) | **confirmed** |
| AB7 | Correction: the agreement count does not move — 29 published and 26 raw on both interpreters. The material new number is the tie count, 13 of 50 published and 12 of 50 raw, which qualifies the agreement figure and is reported beside it | (AI-proposed) | **changed** |

## The paper edit — the theorem subsection

The first prose written at Gate 7, and the only prose written before the
pre-registration was read back. `main.tex:677` becomes 166 lines where it was 14,
because that one subsection carries five of the eight results, three of the nine
debts and seven sentence dispositions. Its shape is fixed by the pre-registration:
the census and the `ask` arithmetic kept, `:681` upgraded from assertion to theorem,
the band claim and the "untested" claim replaced, and the myopia sentence absorbed
here rather than retracted twice.

- **AC1 — the theorem is set in an `amsthm` environment, which the paper did not
  have.** `main.tex` loads `amsthm` at `:35` but declares no `\newtheorem`, and
  `ijcai26.sty` defines no theorem environment either, so `\begin{theorem}` would not
  compile. One line was added to the preamble — `\newtheorem{theorem}{Theorem}` — and
  it is the only edit outside the subsection. `\begin{proof}[Proof sketch]` needs no
  declaration; `amsthm` supplies it. No TeX distribution exists in the working
  environment, so a collision with the kit is unfalsified here rather than ruled out;
  the grep over `ijcai26.sty` finds no `newtheorem`, `theorem` or `proof`, which is
  evidence and not a compile. Kaps holds the compile as a separate verification item
  and is compiling the subsection alone, ahead of the final build, because a broken
  theorem environment blocks every section after it. The fallback if it collides:
  drop the environment, set `\textbf{Theorem 1.}` as a bold run-in with the statement
  in an `\itshape` group, write the sketch as ordinary prose, and hand-set the number
  that `Theorem~\ref{thm:ceiling}` now resolves.

- **AC2 — four trace rows were added to the pre-registration rather than four numbers
  cut from the paper.** The subsection cites the four-arm zero-ceiling count, `raw`'s
  100 distinct `b_h` against `published`'s 8, the 31 raw beliefs below `1/5` of which
  none carries the constraint, and the census reproduced by the VoI analysis. All four
  come from `results/voi-ceiling-arms.json`, which §4.1 did not list. Three of them are
  the *second* half of V2's replacement — quantization is not the cause of `ask`'s
  emptiness — so cutting them would have left the half a reader most wants to doubt
  resting on prose. The §7 falsifier already reads "any number in the paper that cannot
  be named by a key path in §4," so registering them is what puts them under it.

- **AC3 — `6/23` and "two unused actions becomes three" stay out of this subsection.**
  Both are consequences of the reachable-score floor, which D1 places in Results with
  the calibration map and which the required adjacency forbids separating from R7. The
  structural half of the emptiness argument therefore names the floor without its value
  — "the fitted map's reachable range has a floor above `1/5`" — and points forward in
  words. The `\ref` is wired when the Calibration subsection has a label.

- **AC4 — the grid crosscheck is cited in one clause and no more.** It reaches
  `−0.166667` and never exceeds the closed form. The 1185-point plateau and the 115351
  points searched stay in the artifact: once no witness is claimed, the plateau count
  is detail the paper does not need, and Z18 asks for the absence of a witness rather
  than for the arithmetic of the plateau.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AC1 | The theorem is set in an `amsthm` environment; one `\newtheorem` line is added to the preamble, the compile is held as a separate verification item, and the bold run-in fallback is documented in case the kit collides | (AI-proposed) | **confirmed** |
| AC2 | The four `voi-ceiling-arms.json` key paths are registered in §4.1 rather than the numbers being cut from the prose | (Kaps-decided) | **confirmed** |
| AC3 | `6/23` and the three-action consequence stay with R7 in Results; the theorem subsection names the floor without its value and forward-references it | (Kaps-decided) | **confirmed** |
| AC4 | The grid crosscheck appears as "reaches `−0.166667` and never exceeds the closed form", with no argmax point and no plateau count | (AI-proposed) | **confirmed** |

