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
