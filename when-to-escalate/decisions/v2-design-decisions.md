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


## The paper edit — the Calibration subsection

The second prose written at Gate 7, and the last of the two forced-adjacency
sections. `\subsection{Calibration}` keeps v1's reliability diagnosis of the
`needs_human` marginal on 100 cases whole and adds the held-out fit after it, so the
subsection now runs diagnosis, then the fit that tests the diagnosis, then the fit's
own defect. R7 and R8 are one paragraph and one mechanism paragraph, not two results:
the paragraph that reports the three proper scores also reports the `answer` action
disappearing, so neither half can be quoted without the other.

- **AD1 — the three proper scores and the action collapse share a paragraph, and the
  mechanism gets its own.** The required adjacency in §5 says the same subsection; the
  stronger placement was chosen because a subsection can still be quoted a paragraph
  at a time. `\paragraph{A finer belief...}` ends on the census going from three
  actions to two and on the sentence that the second is caused by the first;
  `\paragraph{Why \emph{answer} disappears.}` then carries `6/23`, the ordering
  `1/5 < 3/13 < 6/23`, the 24-of-50-to-0-of-50 crossing count, and the transferable
  form. Splitting cause from effect across a subsection boundary was the failure mode.

- **AD2 — nine more trace rows, not nine numbers cut.** Same disposition as AC2 and
  for the same reason. Two of the nine are costs of the committed map rather than
  results of it — the 0.02-bit rule that let a non-order-preserving map ship, and
  `order_preserved_on_test: false` — and a paper that reports the win without them is
  quoting the selection rule's output while hiding its price. The last row is D4's own
  pair, `published.all_100_reference` against `published.test`, which §5 quotes and
  §4.3 had not registered.

- **AD3 — the 11-of-100 belief drift stays out of Results, and one
  undetermined-cause line is owed to Limitations.** Gate 2's framing rule holds that
  its cause is undetermined, so the only honest sentence about it is that the cause is
  undetermined, which is a limitation and not a result. Results carries the consequence
  at the aggregate level instead: the written-belief row "reaches the same total, mean
  and miss count on this half as its cached beliefs do --- aggregate agreement only,
  not a case-for-case replay." That sentence is true without the number and it blocks
  the reading the number would have corrected. Suppressing it entirely would not be
  honest, so the drift is not dropped but deferred: Limitations owes it one line that
  gives the count and says the cause is undetermined, and that line is a debt of this
  gate until it is written.

- **AD4 — three edits outside the subsection.** `\label{sec:split}` on the
  development-and-test-split subsection, so the closing paragraph can point at the
  matched-by-construction argument rather than restate it; the theorem subsection's
  forward reference wired to `Section~\ref{sec:calibration}`, which AC3 deferred to
  this pass; and U7's prose twin at `:499`, replaced with the same two brackets as the
  caption. U7 is one debt with two false lines, and discharging half of it while
  recording it as discharged is the failure that the split brackets exist to prevent.

- **AD5 — the miss counts carry their denominators as "of 50" and "of 100", and the
  table header carries the population.** D4's rule is discharged three times over: in
  the table's header column, in the caption's caveat sentence, and in the closing
  paragraph, which states outright that the in-sample fit and the population
  restriction produce the same pair of numbers by unrelated routes. The mean is
  labelled as the quantity that may be compared across the two populations and the
  count as the one that may not.

- **AD6 — the table's label is `tab:calibration`.** The internal gate numbering does
  not appear in the paper, in a label or anywhere else.

- **AD7 — the escalation precision and recall of the two re-elicited arms are stated
  in the paper and registered in §4.3.** "The calibrated arm escalates 41 of them" is
  how often the policy escalates; precision falling 0.667 to 0.463 while recall rises
  0.667 to 0.905 is what that costs and what it buys, which is the section's tension as
  numbers rather than as a characterisation. It goes in the same paragraph as the scores
  and the census, immediately before "These are not two findings", so the pair cannot be
  quoted away from the sentence that binds them. Rounded to three decimals to match
  `tab:results`; the sources are `arms.fresh_raw.escalation_precision` and
  `.escalation_recall` in `rebaseline.json` and the same two paths on
  `arms.fresh_calibrated`.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AD1 | R7's scores and R8's action collapse share one paragraph, with the mechanism in the next; the pre-registration's subsection-level adjacency was tightened to paragraph level | (AI-proposed) | **confirmed** |
| AD2 | Nine `logprob-elicitation.json`, `voi-ceiling-arms.json`, `make_figures.py` and `rebaseline.json` key paths registered in §4.3 rather than the numbers being cut | (AI-proposed) | **confirmed** |
| AD3 | The 11-of-100 belief drift stays out of Results; the aggregate-agreement clause carries what a reader needs without asserting a cause, and Limitations owes one undetermined-cause line | (Kaps-decided) | **confirmed** |
| AD4 | Three edits outside the subsection: `\label{sec:split}`, the theorem subsection's forward `\ref`, and U7's prose twin at `:499` | (AI-proposed) | **confirmed** |
| AD5 | Every miss count carries its case set, and the mean is named as scope-invariant where the count is not | (Kaps-decided) | **confirmed** |
| AD6 | The table label is `tab:calibration`; internal gate numbering never appears in the paper | (AI-proposed) | **confirmed** |
| AD7 | Escalation precision 0.667 → 0.463 and recall 0.667 → 0.905 stated in the R7/R8 paragraph and registered as a tenth §4.3 row | (Kaps-decided) | **confirmed** |

## The paper edit — Method, τ and the split

- **AE1 — τ is defined in §Method's metrics, not where it is used.** A threshold on
  `H(b)` in absolute bits is the S4 shape: a numeric rule governing a quantity whose
  scale the rule never consulted. The fix is deciles of the observed `H(b)` on the arm
  being scored, and the reason it is a fix has to sit where the quantity is defined. A
  reader who meets the grid for the first time in the section that reports its cost has
  no way to tell a designed grid from a convenient one.

- **AE2 — the reason is given in the paper's own voice, not by naming the failure
  mode.** The paper says that `H(b)` spans 0 to 2.456 bits with a median of 2.017, so
  an evenly spaced grid over the theoretical range "would report the spacing of the
  grid rather than the behaviour of the rule." That is the whole content of the
  internal name, stated as a property of this distribution and this grid. The internal
  vocabulary stays internal.

- **AE3 — all three definitional consequences are stated in Method.** Repeated
  thresholds on a tied distribution, the same quantile being a different number of bits
  on each arm, and the top decile firing on nothing when an arm's highest-entropy case
  is a development case. Each of the three is a place where a later section could
  present a mechanical consequence of the grid as a result about the rule; stated here
  they are unavailable for that.

- **AE4 — the units constraint is made explicit.** "No quantity in bits is compared to
  a quantity in cost points anywhere in this paper: the entropy selects which cases are
  asked about, and the cost matrix scores what happens." The constraint has held in the
  code since it was set; this is the first sentence in the paper that states it, which
  is what makes it checkable by a reader rather than only by the tests.

- **AE5 — the firing rule is defined by the rule, not by the policy.** The fallback is
  "the cheapest action other than asking", with the coincidence — that on these beliefs
  it is the policy's own action case for case — as a following clause rather than as the
  definition. Defining it as "what the policy would have done" would make the baseline's
  definition depend on the theorem that asking never wins, and the baseline exists to be
  read independently of that.

- **AE6 — τ's consumer is named in words and the `\ref` is owed.** R5's subsection does
  not exist yet, so a `\ref` to it would dangle and break the resolve check run at every
  paper commit. The paragraph says "the entropy-threshold baseline reported below"
  instead. Wiring it is a debt of the next pass, the same debt AC3 carried for
  `sec:calibration`.

- **AE7 — `\subsection{Policies and baselines}` is untouched.** The entropy-threshold
  baseline is not one of the five policies of Table~2 and listing it there would
  misstate what the table reports. The price is that Method names a baseline the reader
  has not met, which is the cost of defining before use and is smaller than the cost of
  a table that says six things and reports five.

- **AE8 — §Method's split subsection gains the fit-and-score assignment, and no
  label.** The map is fitted on the 50 development cases and judged on the 50 test
  cases, so calibrated beliefs on the development half are in-sample and are not
  reported as a result. The existing matched-by-construction caveat is turned both ways:
  it is why close agreement is not generalization, and it is why the halves are an
  acceptable place to fit and score, since the fit cannot be flattered by an easier
  half. No `\label` is added, because nothing points at it yet and an unwritten
  referrer is not a reason to leave an unused label behind.

- **AE9 — six definitional numbers registered in §4.2.** Definitions trace on the same
  terms as results. The one number left unregistered is `[0, \log_2 6]`, which is
  arithmetic on the six-state belief rather than a key path.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AE1 | τ defined in §Method's metrics rather than where it is used | (Kaps-decided) | **confirmed** |
| AE2 | The S4 reason stated as a property of this distribution and grid; the internal name stays internal | (AI-proposed) | **confirmed** |
| AE3 | All three definitional consequences — repeated τ, different bits per arm, top decile firing on nothing — stated in Method | (Kaps-decided) | **confirmed** |
| AE4 | The bits-never-meet-cost-points constraint written into the paper for the first time | (Kaps-decided) | **confirmed** |
| AE5 | The firing fallback defined as "the cheapest action other than asking", with the coincidence with the policy as a clause | (AI-proposed) | **confirmed** |
| AE6 | τ's consumer named in words, no `\ref`; the wiring owed to R5's pass | (Kaps-decided) | **confirmed** |
| AE7 | `\subsection{Policies and baselines}` untouched; the entropy baseline is not one of Table 2's five | (Kaps-decided) | **confirmed** |
| AE8 | §Method's split gains the fit-and-score assignment and the two-way caveat; no `\label` until a referrer exists | (Kaps-decided) | **confirmed** |
| AE9 | Six definitional numbers registered in §4.2; `[0, \log_2 6]` left as arithmetic | (AI-proposed) | **confirmed** |

## The offline compile check, and the figure the README described wrongly

- **AF1 — the preflight becomes a test module, not a scratch script.** It was written to
  answer one question before one commit: does the source carry a defect a compile would
  stop on. Keeping it as a script would mean the answer holds for the version it was run
  against and nothing later. As `tests/paper_preflight.py` with a test module over it,
  every future paper edit is checked before Overleaf sees it, in CI, for free.

- **AF2 — findings split into failures and notes, and notes can never fail a run.**
  Three of the nine checks report things that are not errors: a label nothing
  references (the paper has two on purpose), a control sequence outside the whitelist,
  a `\label` placed before its `\caption`. A module that failed on those would be
  switched off after a handful of edits, and a check that is ignored is worse than no
  check.

- **AF3 — the two false-positive classes are pinned by positive-control tests, not just
  fixed.** The first run reported eleven failures on source that compiles: four were
  inline math legally spanning two lines, six came from a column-spec regex truncating
  `lr p{3.2cm}` at the inner brace, one from not counting a `\multicolumn` span. The
  fixes — parity per blank-line-separated block, a brace-matching spec parser, span
  arithmetic — are each held in place by a test that must stay quiet, because a fix with
  no test against it is one refactor away from coming back.

- **AF4 — a dangling `\ref` is a failure even though it compiles.** LaTeX renders `??`
  and warns. The warning scrolls past in a log nobody reads to the end of and the `??`
  reaches a reader, which makes it exactly the class of defect this module is for. The
  reverse case, a label with no reference, stays a note.

- **AF5 — a check whose external input is absent reports a note and asserts nothing.**
  No `references.bib` beside the source is not evidence that a `\cite` key is wrong, and
  no directory to resolve graphics against is not evidence that a figure is missing. The
  alternative — treating absence as failure — would make the module unusable on a
  fragment and would put a false failure in front of the reader on a real one.

- **AF6 — the module states what it cannot see, in its own docstring and in the
  README.** It cannot see an overfull box, a font substitution, a float landing three
  pages from its reference, or a bibliography style error. A pass means the source is
  structurally sound. It does not mean the paper compiles, and the standing rule that
  the compile is Kaps's falsifier is not softened by having a parser agree with it.

- **AF7 — README step 5 is corrected to match `.gitignore`.** The README said the
  rendered figure is deliberately not committed. `.gitignore` says the opposite in as
  many words — it un-ignores `when-to-escalate/paper/figures/*.pdf` and records
  "committing the rendered figure is the fix", because the figure needs matplotlib,
  which nothing else here depends on, so a clone that had to render it first could not
  compile at all. The README was the file that was wrong and it is the file that
  changed.

- **AF8 — the committed figure's bytes are declared unreproducible rather than claimed
  reproducible, and the timestamp is deliberately not pinned.** `make_figures.py:586`
  calls
  `fig.savefig(out, dpi=300, bbox_inches="tight")` with no metadata argument, so
  matplotlib writes its own version into `/Creator` and `/Producer` and the render time
  into `/CreationDate`. This is measured, not argued: the render of 2026-08-20 is 39907
  bytes and carries `Matplotlib v3.10.8` with `/CreationDate D:20260820194353Z`, and
  Kaps's render of 2026-08-28 00:29 is 27151 bytes and carries `Matplotlib v3.11.1`.
  Same data, same script, two files that share no useful prefix. Step 1 therefore
  excludes this one file from the byte-for-byte comparison
  and step 5 says why, and the values the figure plots are checked instead — by
  `make_figures.py --check` and `tests/test_make_figures.py` against `results/run.json`.
  Both were re-run against the 27151-byte render: `--check` passes, and every plotted
  number still re-derives from `results/run.json`.
  Passing `metadata={"CreationDate": None}` would stop the timestamp moving and leave
  the version strings, and it is declined: the criterion V1 carries is that a clean
  clone builds, which committing the binary satisfies, and byte-stability on a
  renderer's output is not a property worth engineering for. The matplotlib-version
  dependence is recorded as a noted limitation instead.

- **AF10 — a target that names its own extension is only tried as written.** The
  resolver first tried `.pdf` and `.png` for every target, which is right for
  `\includegraphics{fig}` and wrong for `\includegraphics{fig.pdf}` — LaTeX loads what
  the second one names and nothing else. The bug did not stay theoretical: a `.png` from
  a render was sitting in `paper/figures/` while the `.pdf` the paper includes was
  absent, and the check reported the figure present. `GRAPHICS_EXTENSIONS` is now tried
  only for a target that names no extension, and the case has its own test.

- **AF11 — the clean-clone criterion is asked of git, not of the filesystem.**
  `check_graphics` resolves against the working tree, so an untracked file satisfies it,
  and the criterion V1 actually carries is that a fresh clone can compile. That question
  needs `git ls-files`, which the preflight module deliberately does not know about — it
  has to run on a fragment with no repository. So it lives in the test module, as
  `test_every_graphic_the_paper_needs_is_tracked_by_git`, and it fails right now on
  purpose: the rendered figure is still untracked, and it goes green the moment the
  figure is staged.

- **AF9 — the test count in the README moves to 772; the build-log's 712 stays.** The
  two README references are current-state claims and are updated. The `712 passing` in
  the build-log entry of 2026-08-27 was true when that entry was written, and no
  historical row is edited for wording (G9/G12).

- **AF12 — the per-bin count labels are removed rather than repositioned.** The compile
  was green and the figure still carried a visible defect: a stray `35` at
  `(0.200, 0.171)` sitting inside the largest marker and across the curve. The cause is
  in `render()`, not in the data. `ax.annotate` used a fixed `xytext=(0, -3.2)` points
  with `va="center"`, while marker area is `s = 8 + 3.2n` — so the radius runs about
  2.6pt at `n = 4` to about 6.2pt at `n = 35`. A 3.2pt drop clears a 2.6pt radius and
  falls well inside a 6.2pt one, which is why seven bins looked acceptable and the
  eighth looked broken. The rule is a numeric offset governing a quantity whose scale it
  never consulted, and the scale is a function of the very number being printed, so the
  bin that most needs its count legible is guaranteed the worst placement — the same S4
  shape as the tie-break and the τ grid.
  Repositioning is harder than it looks. Two things pass through every marker: the
  Wilson bar, which is vertical and straddles the point (for this bin, `[0.081, 0.327]`
  around an observed 0.171, so up and down are both occupied), and the segment joining
  the bins. Offsetting sideways by the radius does not work here either: `r + pad` is
  roughly 0.04 in data units on this axis, which puts the digits on the dashed
  `3/13 = 0.2308` line. The count is already carried three other ways — marker area,
  the legend entry that names it, and the caption, which states the 4-to-35 range and
  `n = 35` for this bin explicitly — so the labels go and a comment records why, to stop
  a later edit re-adding them with a nudged offset. It also removes the only text in the
  figure that was set at 5.2pt.

- **AF13 — the PNG under `paper/figures/` is ignored; only the PDF is committed.** One
  `savefig` loop writes both extensions, `main.tex` includes the PDF, and nothing reads
  the PNG, so it is an output with no consumer that kept surfacing as untracked work.
  The ignore is written for the PNG alone; the `!…/*.pdf` un-ignore directly above it is
  what a clean-clone compile depends on (AF7) and is untouched.

- **AF14 — the render path has no automated check, and that is why this shipped.**
  `--check` and `tests/test_make_figures.py` verify every plotted *number* against
  `results/run.json` and neither imports matplotlib; nothing verifies *placement*. Both
  were green with the stray label on the page. No test is added for the removal: the
  assertion worth making is about pixels, matplotlib is absent from this environment,
  and a test asserting that a particular `annotate` call is missing pins the fix rather
  than the property. The gap is recorded rather than papered over — the figure's
  appearance is checked by a human reading a compiled PDF, and this defect was found
  that way.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AF1 | The offline preflight ported into `tests/` as its own module plus 60 tests | (Kaps-decided) | **confirmed** |
| AF2 | Findings split failures / notes; notes never fail a run | (AI-proposed) | **confirmed** |
| AF3 | Both false-positive classes held down by positive-control tests, not only fixed | (AI-proposed) | **confirmed** |
| AF4 | A dangling `\ref` is a failure; an unreferenced label is a note | (AI-proposed) | **confirmed** |
| AF5 | A check with no external input to read notes and asserts nothing | (AI-proposed) | **confirmed** |
| AF6 | The module and the README both state that a pass is not "it compiles" | (Kaps-decided) | **confirmed** |
| AF7 | README step 5 corrected to match `.gitignore`: the figure is committed so a clean clone builds | (Kaps-decided) | **confirmed** |
| AF8 | The figure PDF excluded from byte-for-byte reproduction with the reason stated; committed as a binary artifact and `/CreationDate` deliberately not pinned | (Kaps-decided) | **confirmed** |
| AF9 | README test count 712 → 772; the build-log's historical 712 untouched | (Kaps-decided) | **confirmed** |
| AF10 | An `\includegraphics` target naming its own extension is resolved only as written | (AI-proposed) | **confirmed** |
| AF11 | The clean-clone criterion asked of `git ls-files` in the test module, not of the filesystem in the check | (AI-proposed) | **confirmed** |
| AF12 | The per-bin count labels removed from the reliability figure rather than repositioned; the count stays in marker area, legend and caption | (Kaps-decided) | **confirmed** |
| AF13 | `paper/figures/*.png` ignored; the `*.pdf` un-ignore left alone | (Kaps-decided) | **confirmed** |
| AF14 | No test added for the label removal; the untested render path recorded as the reason the defect shipped | (AI-proposed) | **noted** |

## The paper edit — Limitations

- **AG1 — the myopia retraction is written once, in Limitations, and the other two
  live passages get consistency edits that carry no retraction language.** Z6 fixed
  the canonical site as the place v1 made the claim. The two edits at
  `paper/main.tex:250` (Related work) and `:347` (Agent design) now state the result —
  a one-step rule cannot price the belief a question buys, and on this matrix that
  costs nothing — and point at `sec:unused`. Neither says anything is withdrawn. The
  falsifier is five wordings of one retraction, and the way to fail it is to let each
  site apologise for itself.

- **AG2 — the retraction is decomposed rather than reversed wholesale.** Three parts,
  and only one of them goes. Withdrawn: that `ask` is undervalued here, that computing
  its value of information is the honest handling this design omits, and that its
  absence from the census follows from the horizon. Kept: the policy is myopic and
  carries no machinery that prices a question's downstream value — a true statement
  about the implementation, and still a limitation of it. Residual scope, which is the
  part that is new: the collapse is a property of this cost matrix, and the policy
  never checks the property it depends on, so what is safe here is safe for a reason
  the code does not verify.

- **AG3 — both misreadings of the theorem are named in the Limitations text, not left
  to the theorem section.** `2/13` is a floor on the gap and not an estimate of its
  size; the theorem bounds one more question inside a deeper policy on this matrix and
  this action menu, not the value of interaction design. Two §7 falsifiers point at
  exactly these, and a retraction paragraph is where a reader most likely over-reads
  the result in the paper's favour.

- **AG4 — the reachable-range sentence is worded off the bare word "floor".** Z9
  reserves that word: the residual-miss floor is a count and the reachable-score floor
  is a probability, and neither may appear bare. The structural-emptiness clause now
  reads "whose reachable range starts above $1/5$". The one remaining "floor" in the
  section is "a floor on the gap", which is a third object and carries its noun.

- **AG5 — L1's two carried caveats get their own Limitations paragraph rather than
  being left in Results.** A reader who reads only the Limitations section would
  otherwise meet neither. The paragraph states both at full strength with the numbers
  §6 already reports — the cost result is against the uniform baseline only, the
  always-notify comparison is a near-tie at 1.72 against 1.74, the win is human load
  at 43 escalations of 100 against all 100 and precision 0.605 against 0.420; and the
  dev/test totals agree because the split was matched by construction, so they are not
  out-of-sample evidence. Nothing is hedged into a softer form on the way across.

- **AG6 — OQ3 is written as a bounded result, and the bound is the theorem's
  answer-model independence.** The check simulates replies from the design's own model
  of the lead, so it is a self-consistency check of the implementation and is named
  that; it is never called a validation and never described as out-of-sample. What
  makes it a scope statement rather than a hedge is the next sentence:
  `Theorem~\ref{thm:ceiling}` does not use the answer model at all, needing only
  non-negativity of `Table~\ref{tab:costs}`, so what the missing external evidence
  touches is the per-case ceilings and the count of resolving questions — not the
  result that `ask` is never selected. S1's correction stays in this record and is not
  folded back into OQ3's text.

- **AG7 — abstention gets its own entry, framed as priced out under this matrix.** New
  at this pass and not in the approved plan. The argument is column-wise dominance of
  `escalate-pause` by `escalate-notify` in all six columns by between 1 and 3, which is
  already in §6.3, so no number is computed here. The scope qualifier is the matrix:
  the costs are expert-set rather than measured and §4 shows at least one magnitude is
  load-bearing, so a matrix in which pausing is not dominated makes abstention
  available again and this experiment says nothing about that case. The census fact
  that `escalate-pause` is never selected moves here from the myopia sentence, which is
  where it had been doing duty as evidence for the horizon claim.

- **AG8 — the drift line gives the count and stops.** AD3 owed Limitations one line.
  It reads 89 of 100 unchanged, 11 different, none unparseable, and says the record
  does not determine the cause. The three numbers come from `results/rebaseline.md` and
  `reproduction_check.unparseable` in `results/logprob-elicitation.json`. The cause is
  not attributed to the calibration map, and the resolved-snapshot half of L10 is left
  out: v1 stored the alias, so "no dated snapshot is recorded" is the true statement
  about the beliefs this paper reports, and naming v2's snapshot beside it would read
  as though the reported numbers had one.

- **AG9 — the reproducibility paragraph carries the interpreter floor.** A §7 falsifier
  is a reproducibility claim in the paper without it. The paragraph names Python 3.12,
  the reason (compensated summation over floats), the two float-bearing artifacts
  compared to $10^{-9}$ rather than exactly, and the figure's exclusion from the byte
  comparison with the renderer-metadata reason. It closes on the boundary that matters
  most: the belief cache is an input to the experiment, not an output of it.

- **AG10 — the section's counted enumeration is dropped.** "Two limitations are
  structural" became "Several", and "A third structural limitation" became "A further".
  A fixed count in the lead sentence breaks silently every time an item is added, and
  the count carried no information.

- **AG11 — the Conclusion's myopia passage is not touched at this pass.** It is the
  fifth of the five passages and the map assigns it a replacement by the answer rather
  than a retraction. Editing it here would put two retraction-shaped paragraphs in the
  same commit, which is how the "written more than once" falsifier gets tripped.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AG1 | The myopia retraction written once in Limitations; `:250` and `:347` get consistency edits with no retraction language | (Kaps-decided) | **confirmed** |
| AG2 | The retraction decomposed into withdrawn, kept, and residual scope rather than reversed wholesale | (AI-proposed) | **confirmed** |
| AG3 | Both misreadings of the theorem named in the Limitations text: `2/13` is a floor on the gap, and the scope is this matrix and this menu | (AI-proposed) | **confirmed** |
| AG4 | The structural-emptiness clause reworded off the bare word "floor" per Z9 | (AI-proposed) | **confirmed** |
| AG5 | L1's two carried caveats given their own Limitations paragraph, at full strength | (Kaps-decided) | **confirmed** |
| AG6 | OQ3 written as a bounded result, scoped by the theorem's independence from the answer model; never called validation or out-of-sample | (Kaps-decided) | **confirmed** |
| AG7 | Abstention added as its own entry, priced out under this matrix by column-wise dominance, with the expert-set-costs scope | (Kaps-decided) | **confirmed** |
| AG8 | The drift line gives the count and the undetermined cause only; the resolved-snapshot half of L10 left out | (AI-proposed) | **confirmed** |
| AG9 | The reproducibility paragraph carries the Python 3.12 floor | (Kaps-decided) | **confirmed** |
| AG10 | The section's counted enumeration dropped: "Two limitations" → "Several", "A third" → "A further" | (AI-proposed) | **confirmed** |
| AG11 | The Conclusion's myopia passage left for its own pass | (AI-proposed) | **noted** |

## The paper edit — the abstract's calibration sentence

- **AH1 — the abstract now carries the trade-off, not the halving alone.** Raised as
  "AH6" in the instruction that found it; this record has no AH block before this row,
  so it is AH1. The sentence at `paper/main.tex:116` said recalibration "halves the
  misses, from 16 to 8" and then went straight to the residual 8. §7.3 states the same
  change two-sidedly — escalations 43 to 60, precision 0.605 to 0.567, and a
  composition of 9 fixed against 1 new miss created — so the defect was the summary
  keeping the flattering half of a paragraph written not to have one. The abstract is
  what is read, and a one-sided abstract over a two-sided body is a one-sided paper.

- **AH2 — the correction runs the other way on cost.** The instruction asked for "cost
  up". Cost falls: `recalibration.before.mean_cost` is 1.650 and
  `recalibration.after.mean_cost` is 1.250 in `results/robustness.json`, and §7.3 says
  so. What rises is load, and that is the whole trade-off — escalations and precision,
  not cost. Writing "cost up" would have put a number in the abstract that contradicts
  the body and the artifact.

- **AH3 — the two cost figures are named directionally rather than numerically.** The
  abstract already quotes 1.72, which is the legacy tie-break total; the recalibration
  pair is 1.650 to 1.250 against the corrected baseline. Printing 1.650 eight lines
  under 1.72 with no room to explain which baseline is which trades one confusion for
  another, so the abstract says mean cost falls and §7.3 carries the pair.

- **AH4 — every count in the new sentence carries its denominator.** Z8 applies inside
  the abstract too: "16 to 8" became "on those 100 cases, 16 to 8", escalations read
  "43 of 100 to 60", and the composition reads "9 of the 16". The in-sample label is
  kept, which is what Z11 requires: the sentence is extended, not replaced.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AH1 | The abstract carries the calibration trade-off, not the miss halving alone; registered as falsifier Z19 | (Kaps-decided) | **confirmed** |
| AH2 | "Cost up" corrected to cost down, 1.650 to 1.250; the trade-off is load, not cost | (Kaps-decided) | **confirmed** |
| AH3 | The recalibration cost pair named directionally in the abstract, numerically in §7.3, to avoid two baselines in one paragraph | (AI-proposed) | **confirmed** |
| AH4 | Every count in the new abstract sentence carries its denominator per Z8; the in-sample label kept per Z11 | (AI-proposed) | **confirmed** |

## The paper edit — the abstract reframed off the miss count

- **AH5 — AH1 to AH4 are superseded inside the same pass.** The trade-off framing
  kept the halving in the abstract and made it two-sided by adding the load it is
  bought with. The instruction that followed removes it instead: the abstract states
  the calibration result as a calibration-quality improvement scoped by the
  reachable-score floor, cites the held-out measures, and carries no miss count at
  all. The four earlier rows stay as written because they record what was tried.

- **AH6 — two premises were given for the reframing and one of them does not hold.**
  Both are recorded because the conclusion is adopted and the reasoning is not.
  - *"The abstract's 16 to 8 is the train/test split artifact, not recalibration's
    effect."* Not what the artifact says. `recalibration.before.misses` is 16 and
    `recalibration.after.misses` is 8 in `results/robustness.json`, both on the 100
    cases, so the pair is recalibration's measured in-sample effect and the abstract
    attributed it correctly. The real defect is that restricting the same policy and
    the same beliefs from those 100 cases to the 50 test cases *also* prints 16 to 8
    (`paper/main.tex:1082`), so two unrelated operations produce an identical string
    within sight of each other. That is a confusability failure — D4's shape, which
    Z8 names — not a false attribution.
  - *"The floor sits above both thresholds so recalibration cannot improve the
    decision on this matrix."* True of the held-out isotonic map and false of the
    in-sample fit, which are different objects. The isotonic map's lowest pooled
    block puts its reachable-score floor at `6/23`, above both `3/13` and `1/5`, so
    `answer` is unreachable and §6.6's action census loses it. The in-sample
    recalibration is a bin map, and `recalibration.mapping` in
    `results/robustness.json` sends the `0.2-0.3` bin to `0.1714`, below `3/13`. It
    can and does change decisions: misses 16 to 8, escalations 43 to 60, mean cost
    1.650 to 1.250. Recalibration improves the decision in-sample. What it cannot do
    is generalise, which is a different objection and the one that holds.

- **AH7 — the reframing is adopted on the ground that survives AH6.** Not that the
  in-sample result is unreal, but that the abstract had the weaker of the two
  calibration results in it. §6.6 fits on 50 development cases and scores the other
  50; §7.3 fits and scores on the same 100. Held out beats in-sample, and the
  held-out result is also the more interesting one, because the gain stops at the
  map's range rather than at the data. The abstract now carries that.

- **AH8 — no miss count survives in the abstract.** Checked by reading every numeral
  in `paper/main.tex:85-133`. What is left is 100 and 50 as set sizes, the cost
  figures 1.72, 2.58, 1.74 and the gap 0.86 to 1.07, the escalation count 43 of 100,
  the in-sample ECE 0.142 with its interval, the three held-out measures, the two
  rationals, and the held-out precision and recall. No count of misses, fixes, or
  survivors appears.

- **AH9 — the in-sample sentence keeps its scope label and loses its count.** Z11
  required that sentence to be kept and extended rather than replaced, on the ground
  that it is true and v1 labelled its own scope. Half of that survives: the abstract
  still says recalibrating the marginal on the same 100 cases is an in-sample ceiling
  and that the body reports it as one, which is the scope claim. The number it was
  extended with is gone. Z11 is resolved the other way and registered as Z20.

- **AH10 — the abstract prints §6.6's own digits.** The instruction gave ECE as 0.153
  to 0.070; §6.6 prints 0.1526 to 0.0696. The abstract uses the body's four decimals
  so a reader comparing the two finds the same string rather than a rounding they have
  to reconcile. Cross-entropy 0.8546 to 0.8136 bits and Brier 0.2063 to 0.1962 are
  carried as well, because "all three measures named in advance" is the claim and one
  of the three alone does not support it.

- **AH11 — the paragraph now holds two ECE values, so both carry their population.**
  0.142 is on all 100 cases with the published beliefs; 0.1526 and 0.0696 are on the
  50 test cases with the re-elicited ones. The second pair is introduced as "on those
  50 test cases" for that reason. Same rule as Z14's caption requirement, applied to
  prose.

- **AH12 — R7 and R8 travel together into the abstract.** Z10 requires them in the
  same subsection; putting R7 in the abstract without R8 would break the rule at the
  one place it matters most. The floor sentence is therefore not a caveat attached to
  the result, it is half of the result, and the paragraph closes on the join: a
  calibration-quality gain that the map's range prevents from becoming a decision
  gain. "Reachable-score floor" keeps its qualifier, per Z9.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AH5 | AH1-AH4 superseded within the same pass: the abstract carries no miss count rather than a two-sided one | (Kaps-decided) | **changed** |
| AH6 | Both premises recorded; the split-artifact claim does not hold and the floor claim holds only for the held-out isotonic map, not the in-sample bin map | (AI-proposed) | **noted** |
| AH7 | The reframing adopted because the abstract held the weaker of the two calibration results, not because the in-sample one is unreal | (AI-proposed) | **confirmed** |
| AH8 | Zero miss counts in the abstract, verified numeral by numeral over `:85-133` | (Kaps-decided) | **confirmed** |
| AH9 | The in-sample sentence keeps its scope label and loses its count; Z11 resolved the other way as Z20 | (Kaps-decided) | **changed** |
| AH10 | The abstract prints §6.6's four decimals, and all three measures rather than ECE alone | (AI-proposed) | **confirmed** |
| AH11 | Both ECE values in the paragraph carry their population, 100 published against 50 test re-elicited | (AI-proposed) | **confirmed** |
| AH12 | R7 and R8 enter the abstract together per Z10; the floor is half the result, not a caveat | (AI-proposed) | **confirmed** |


## The paper edit — Conclusion

- **AJ1 — the prefix skips AI.** The next letter pair after AH is AI, and every table
  in this file carries "(AI-proposed)" in its provenance column. A row id that
  collides with the provenance vocabulary is a search hazard, so this block is AJ.

- **AJ2 — the ask paragraph is replaced by the answer, not by a retraction.** The map
  files the Conclusion passage as REPLACED by the answer and says why: v1 asked
  exactly the question v2 settles — "whether the action is genuinely useful or merely
  unpriced" — and a question a paper poses and its successor answers is a result. So
  the paragraph opens on the question being closed and gives the answer as neither: it
  was priced, and it lost. No retraction language appears anywhere in the Conclusion.
  Y5b's falsifier is the claim withdrawn in five wordings; it is withdrawn once, in
  Limitations, and the Conclusion points at the theorem instead.

- **AJ3 — the myopia passage lands as the proven claim, not as a hedge.** This is the
  paper's last word on asking and the thing it must not say is that the horizon is
  what excluded the action. v1's version said a myopic policy cannot price asking
  "because that value is a better belief next turn," which reads as an admission. The
  replacement states the bound first — at most $-2/13$ at every belief in the simplex
  on the unconstrained menu, attained at the all-hot vertex — then closes the horizon
  question with depth-independence: posteriors are beliefs, the bound holds at every
  node of a lookahead tree, and $W_k = V_{\mathrm{act}}$ for every $k \ge 1$. Two
  sentences carry the whole point and are deliberately short: "Asking does not fail
  here because the policy looks only one step ahead. It fails at every depth." The
  one-step rule is still named as a rule that does not price downstream value; what is
  gone is the inference that its not doing so is why *ask* is absent.

- **AJ4 — R2 is restated in the Conclusion as the portable claim.** The map assigns it
  there and the second paragraph of the ask entry carries it: $c_F/\nu + c_T/\alpha <
  1$ in words as well as symbols, the $16/15$ that fails it, the 6.25\% margin, the
  $15/16$ scaling that puts the ceiling at zero, and the designer with a cheaper
  question who is on the other side of the line. The transfer claim is the inequality,
  not the $-2/13$.

- **AJ5 — the binding wording rule holds and the carve-out is referenced, not
  restated.** Every claim in the passage says "on the unconstrained action menu" or
  "on this matrix, and on the unconstrained menu." The constrained-menu positive
  region is named as existing and as unoccupied — "a region of hot beliefs that no
  case in this set occupies" — with the derivation left in the theorem section.
  Restating $b_h < 1/5$ and the $+1$ ceiling in the Conclusion would be a second,
  thinner version of a committed passage, which is the duplication the map warns
  about.

- **AJ6 — the calibration entry discharges KEPT-AND-PROVEN.** v1's causal claim is
  that the residual-miss floor is set by the granularity of the elicitation and not by
  the calibration method. Gate 2 did what v1's own next sentence named as the next
  step — a finer belief and a held-out fit — and the claim held, so the entry says it
  can now be reported as tested rather than asserted. v1's "the next step is" becomes
  a reference to Section~\ref{sec:calibration}, since the step was taken. This is the
  one place in the paper where the earlier draft predicted correctly, and it is filed
  as a result rather than left reading as an open plan.

- **AJ7 — the held-out miss pair is 7 to 2 of 50, not 8 to 2.** The pre-registration's
  D1 discussion says Gate 2 moved misses "8 → 2 on the same 50 test cases".
  `tab:calibration` gives the re-elicited uncalibrated arm 7 misses of 50 and the
  calibrated arm 2; the 8 is the *written-belief* arm on that half, a third row. So
  the pre-reg states a before-and-after across two different arms. The Conclusion uses
  the table's 7 to 2, both counts carrying the 50. The pre-reg row is left as written,
  since no historical row is edited for wording, and this is the correction on the
  record.

- **AJ8 — Z10 is honoured inside the Conclusion.** R7 without R8 anywhere is a gate
  failure, so the sentence reporting what breaking the floor cost — mean 1.40 to 1.50,
  41 of the 50 escalated — carries the mechanism in the same breath: a PAVA-fitted map
  cannot emit a score below its lowest pooled block's positive rate, and the threshold
  for answering lies underneath. `6/23` itself is not re-derived here; the object is
  named and Section~\ref{sec:calibration} holds the arithmetic.

- **AJ9 — four bare-"floor" sites fixed, and the naming in the instruction
  corrected.** The instruction identified `:1209`, now `:1220` after the abstract
  grew, as the `6/23` object. It is not. That sentence closes §7.3, which is the
  in-sample bin map on 100 cases, and its antecedent is the clause before it: 8 misses
  that recalibrating this marginal cannot remove. A count, on 100 cases, which is Z9's
  residual-miss floor, and V3 assigns that object to the Conclusion and to in-sample
  Results while `6/23` stays in the Calibration subsection. Naming it "reachable-score
  floor" would have moved §6.6's probability onto §7.3's count — the same two-maps
  collapse twice corrected already this pass. Fixed: `:1220` and `:1458` and `:1466`
  to "residual-miss floor", `:870` to "reachable-score floor". Left alone: `$2/13$ is
  a floor on the gap` at `:837` and `:1311`, which is a third object and qualified by
  AG3, and the Python floor at `:1385`, which is a different word.

- **AJ10 — the three-questions sentence no longer calls all three open.** With one
  closed and one mostly answered, "Three questions follow directly from these results"
  alone overstated what is outstanding. It now names the split. Raised in the plan as
  an addition beyond the map rather than folded in silently.

- **AJ11 — what the pass did not touch.** The turn-boundary entry, which is
  KEPT-AS-LIMITATION and which `v2-policy-boundary.md` part 4 depends on; the summary
  paragraph; the AI-use statement. AG11 is discharged by this pass and its status
  stays **noted** as the deferral it recorded.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AJ1 | Block prefixed AJ, skipping AI, which collides with the provenance column | (AI-proposed) | **confirmed** |
| AJ2 | The ask paragraph replaced by the answer with no retraction language, per the map and Y5b | (Kaps-decided) | **confirmed** |
| AJ3 | The myopia passage lands as the proven claim: the bound first, then depth-independence, never "we did not look far enough ahead" | (Kaps-decided) | **confirmed** |
| AJ4 | R2 restated in the Conclusion as the portable condition, in words and symbols, with the 6.25% margin | (AI-proposed) | **confirmed** |
| AJ5 | Binding wording rule everywhere; the constrained carve-out referenced and its emptiness named contingent, not re-derived | (Kaps-decided) | **confirmed** |
| AJ6 | KEPT-AND-PROVEN discharged: v1's granularity claim reported as tested, and its "next step" turned into a reference | (AI-proposed) | **confirmed** |
| AJ7 | The held-out pair is 7 to 2 of 50; the pre-reg's "8 → 2" crosses two arms and is left as written | (AI-proposed) | **noted** |
| AJ8 | R8's mechanism travels with R7 inside the Conclusion per Z10; `6/23` not re-derived there | (AI-proposed) | **confirmed** |
| AJ9 | Four bare-"floor" sites qualified; `:1220` is the residual-miss count, not `6/23`, against the instruction's naming | (AI-proposed) | **changed** |
| AJ10 | The three-questions sentence names one closed, one mostly answered, one open | (Kaps-decided) | **confirmed** |
| AJ11 | Turn boundary, summary paragraph and AI-use statement untouched; AG11 discharged | (AI-proposed) | **confirmed** |
| AJ12 | Z21 registered against future-work prose promising what the theorem disproves; the sentence it was raised against does not exist in `main.tex`, so the rule is prospective | (Kaps-decided) | **noted** |

## The paper edit — the Introduction and Related Work read against the rewrites

The section-by-section pass worked forward from the theorem section, so everything
before it was still v1 prose. Read end to end against the rewritten sections, `:1`
through `:742` carried twelve inconsistencies: five contradictions, three
under-qualifications, two mis-descriptions of the paper itself, and two declaration
gaps. All twelve are fixed in one pass. Two of the four items the instruction named
could not be done as specified, and the reason is recorded rather than worked around.

- **AK1 — the block is prefixed AK, not AJ.** AJ1–AJ12 are committed against the
  Conclusion, and the instruction's AJ1–AJ8 point at findings from this read instead.
  Reusing the prefix would give two different decisions the same identifier in the
  same document, which is the one thing an index cannot survive. AK continues the
  sequence.

- **AK2 — the band claim the instruction asked to replace is not in the Introduction,
  and no sentence before the theorem section makes it.** The two sites named, `:104`
  and `:683`, are the abstract's uniform-baseline sentence and a row of
  `tab:results`; neither mentions asking. Across the whole file "band" appears once
  before the theorem section, now `:565`, and it is a different and true claim: every
  threshold in (0.2, 0.3] produces identical decisions on these cases, so `3/13` is
  one arbitrary point inside a band the measurement cannot resolve. That is a band of
  thresholds, not a region where a question wins, and the theorem does not touch it.
  Replacing it with "no band, max −2/13" would have deleted a true statement and
  substituted a claim about a different quantity. Left as written.

- **AK3 — the instruction's content was written into the Introduction as an addition
  instead.** The defect it was aimed at is real and larger than one sentence: nothing
  in `:1`–`:742` mentioned the theorem, the ceiling, `2/13`, value of information,
  `c_F/ν + c_T/α < 1` or `1/5`, all six of which grep to zero hits there. The reader
  met the paper's one data-independent result with no preparation for it. The new
  paragraph states the bound at every belief in the simplex, that there is no narrow
  middle band in which asking wins, that the coarseness of the elicited belief is not
  what hides one, horizon-independence, the portable condition with its 6.25% margin,
  and the constrained carve-out at `b_h < 1/5` on the hot ray with its emptiness in
  this set. An addition, not a replacement, and flagged as one because the map does
  not carry it.

- **AK4 — the scope overclaim.** "We report both comparisons rather than only the
  favourable one" was true of v1 and false of v2, which has three. The uniform
  baseline's equivalence to a plain 0.5 threshold on all 100 cases now appears in the
  Introduction, where it weakens the 1.72-against-2.58 gap at the point the gap is
  first claimed, and the threshold sweep that selects escalate-everything is named as
  the third and least favourable comparison. The abstract already carried the first
  qualifier; the Introduction did not.

- **AK5 — "the fix is recalibration, not a redesign of the state" is withdrawn.** The
  AI7 shape at the top of the paper: a direction the later sections disprove. It is
  now "the first fix to try", which is what §7 says, and the held-out outcome travels
  with it in the same paragraph — all three measures improve and the policy stops
  choosing *answer* at all, because the map cannot emit a probability low enough.
  Stated without the cost and miss numbers, because on that half misses do fall 7 to
  2 while mean cost rises 1.40 to 1.50, and "changes no decision for the better" would
  be false.

- **AK6 — "under-confident in exactly the range that suppresses escalation" is
  deleted.** §7 puts that phrase in quotation marks to reject it: the bin containing
  `3/13` is the one that reads slightly over-confident, with a Wilson interval
  covering its prediction, and the under-confidence is in its neighbours. The
  Introduction had been half-patched — "in two of the bins nearest the threshold" is
  right — and then re-asserted the rejected phrasing in the same sentence.

- **AK7 — the sign collision on calibration, two sites.** Related Work and the Agent
  design's Belief paragraph both said overconfidence is "exactly the failure the
  results show", while §7 measures under-confidence on the marginal that decides.
  Both words are used as measured predicted-against-observed directions throughout
  §6.6 and §7, so a reader carried the wrong sign into the results. The `guo2017`
  finding stays theirs and stays as they report it; what this
  paper measures is now stated as its own direction — a needs-human probability read
  too low, which is under-confidence against observed frequency. Pre-existing in v1,
  not created by the rewrites.

- **AK8 — the second Y5b site.** The Agent design's Policy paragraph said *ask*'s
  value "is mostly the better belief it buys next turn, which a one-step rule cannot
  see". Both halves are refuted by the sections that came after it: the necessary
  condition for positive value of information fails at every belief, so asking loses
  on its fee before any continuation is counted, and it still loses by the full
  ceiling on the 16 published pairs where the continuation term is exactly zero. The
  shipped policy is `W_1`, which does price the continuation. Replaced with the fee
  mechanism. Y5b's falsifier is the claim withdrawn once, in Limitations; this was a
  re-assertion of it 900 lines earlier.

- **AK9 — there are no bare-"floor" stragglers before the theorem section.** The
  instruction called this the last batch surfaced by the back-to-front read. It is
  empty: "floor" occurs once in `:1`–`:742`, at `:123`, and it is the qualified
  reachable-score floor in the abstract, written that way in the abstract pass. This
  was reported at the end of the previous pass and is recorded here rather than
  answered with an edit.

- **AK10 — the roadmap named neither spine.** It listed six sections and skipped
  `sec:unused` and `sec:calibration`, so the impossibility theorem and the held-out
  fit were both unannounced. Both are subsections of Results, so they are named
  inside that clause rather than given their own sentences.

- **AK11 — Metrics declared one of three measures.** §6.6 reports "all three proper
  scoring rules named in advance"; the subsection where the paper says what it
  measures listed expected calibration error alone. Cross-entropy and Brier are now
  declared there, scoped to the held-out fit and marked as fixed before it. The L10
  shape: a claim whose conditions the artifact does not record.

- **AK12 — the bare 0.142.** AH11 attached populations to both expected calibration
  errors in the abstract because §6.6 reports 0.1526 on the re-elicited test half.
  The Introduction's unqualified 0.142 is the same confusability, D4's shape rather
  than falsity, and now carries "of those 100 cases".

- **AK13 — "it has a known cost of its own".** Related Work sent the reader to
  Limitations for a cost that Limitations withdraws: what survives there is that
  being myopic is safe on this matrix, with the cost hypothetical on a matrix
  satisfying the condition. The paragraph self-corrected two sentences later, so only
  the framing was wrong. Rewritten to make the cost conditional from the start.

- **AK14 — what the pass did not touch.** The threshold band at `:565`, which is true
  and about a different object (AK2); the problem-statement seed and its note, which
  are verbatim by rule; the abstract, which was rewritten in its own pass; and every
  section from the theorem onward, all of which this read used as the reference.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AK1 | Block prefixed AK; the instruction's AJ1–AJ8 collide with the committed Conclusion rows | (AI-proposed) | **changed** |
| AK2 | No band claim about asking exists before the theorem section; `:104` and `:683` are the abstract's baseline sentence and a table row; `:565`'s threshold band is true and left as written | (AI-proposed) | **changed** |
| AK3 | The theorem written into the Introduction as an addition: no band, ≤ −2/13 everywhere, coarseness not the cause, horizon-independent, the condition, the carve-out at `b_h < 1/5` | (Kaps-decided) | **confirmed** |
| AK4 | Three comparisons, not two; the 0.5-threshold equivalence moved to where the gap is first claimed | (Kaps-decided) | **confirmed** |
| AK5 | "The fix is recalibration" → "the first fix to try", with the held-out outcome in the same paragraph and no cost or miss numbers | (AI-proposed) | **confirmed** |
| AK6 | "Under-confident in exactly the range that suppresses escalation" deleted; §7 rejects that phrase by name | (AI-proposed) | **confirmed** |
| AK7 | The overconfidence/under-confidence sign fixed at both sites; guo2017's finding left as theirs | (AI-proposed) | **confirmed** |
| AK8 | *Ask*'s value is not mostly the next-turn belief and a one-step rule does price it; replaced by the fee mechanism | (AI-proposed) | **changed** |
| AK9 | No bare-"floor" instances exist before the theorem section; the batch is empty | (AI-proposed) | **noted** |
| AK10 | The roadmap now names `sec:unused` and `sec:calibration` | (AI-proposed) | **confirmed** |
| AK11 | Metrics declares cross-entropy and Brier alongside ECE, scoped to the held-out fit | (AI-proposed) | **confirmed** |
| AK12 | The Introduction's 0.142 carries its population, per AH11 | (AI-proposed) | **confirmed** |
| AK13 | Related Work's "known cost of its own" made conditional, matching what Limitations leaves standing | (AI-proposed) | **confirmed** |
| AK14 | `:565`, the problem-statement seed, the abstract and everything from the theorem onward untouched | (AI-proposed) | **confirmed** |

## The paper edit — naming the baseline behind the cost win

The cost result is a comparison against two baselines that answer in opposite
directions: a reduction of a third against the uniform-cost baseline, and no
reduction at all against always-notify. Every site stating the first is now
required to name which baseline it is against, and every site stating a
human-load number is required to name the population it is counted over. Both
are the D4 discipline — a numeric claim whose scale or denominator the claim
never states — applied to the two places the paper is easiest to misread.

Three rulings arrived before this pass proposing that `2.58` be deleted, that it
was `always_notify` misattributed, and that it was a cross-population figure
compared against a test-split number. `results/run.json` refuted each. The
recorded ground truth, same population, `summaries.test`, n = 50:
`policies.cost_aware.mean_cost = 1.72` (`total_cost` 86),
`policies.always_notify.mean_cost = 1.74` (87), and
`policies.uniform_baseline.mean_cost = 2.58` (129). The same three means hold at
`summaries.dev` and `summaries.all`, because the halves were stratified by
archetype and sub-variant and balanced on the needs-human count. There is no
`summaries.hard` key; `summaries` holds exactly `dev`, `test`, `all`. So no cost
comparison in the paper was cross-population, and the locked always-notify caveat
matched the artifact on a single population and was confirmed rather than revised.

The uniform baseline is not random. `src/costs.py:109-112` derives `UNIFORM_COST`
by replacing every non-zero cost with `1.0`, holding the belief, the feasible set
and the expected-cost machinery fixed. "Uniform-random" was proposed for the
falsifier and is not written anywhere, because it would misdescribe the control.

| # | Decision | Provenance | Status |
|---|---|---|---|
| AL1 | Block prefixed AL; AK1–AK14 are the Introduction read-back and this is a separate pass | (AI-proposed) | **confirmed** |
| AL2 | `2.58` kept at every site: it is `uniform_baseline`, same population as every other headline cost, and the design's only control for the asymmetry | (Kaps-decided) | **changed** |
| AL3 | The paper is not re-led on the theorem and the reachable-score floor; the uniform-baseline cost win is real and stays a reported result | (Kaps-decided) | **changed** |
| AL4 | The locked always-notify caveat confirmed against `summaries.test`, not revised: 172 against 174 over 100, one point in 87 on each half | (Kaps-decided) | **confirmed** |
| AL5 | Both baselines named wherever the cost win appears — abstract, Introduction, §7.1, Conclusion — so `2.58` cannot read onto always-notify | (Kaps-decided) | **confirmed** |
| AL6 | "A reduction of a third" never stated without naming the uniform-cost baseline in the same sentence or the next | (Kaps-decided) | **confirmed** |
| AL7 | §7.2's threshold sweep labels its populations: the `t = 0.35`/`t = 0.25` bracket is all 100, the tuning is the 50 development cases | (AI-proposed) | **confirmed** |
| AL8 | The dev-tuned selection disclosed as dev-specific — on the test half `t = 0.05` and `t = 0.10` cost 1.68 against `t = 0.00`'s 1.740 | (AI-proposed) | **noted** |
| AL9 | Human-load numbers carry their population: 43 of 100 and 0.605 against 0.420 are all-100; the test half is 20 of 50 at 0.65 against 0.42 | (Kaps-decided) | **confirmed** |
| AL10 | No interval is claimed on the always-notify cost difference, because none was computed; `robustness.json` bootstraps ECE only | (AI-proposed) | **confirmed** |
| AL11 | `\label{sec:tie}` added so §7.1 can point at the near-tie subsection rather than restating it | (AI-proposed) | **confirmed** |
| AL12 | "Uniform-random" not written anywhere; the baseline replaces every non-zero cost with one and is not random | (AI-proposed) | **changed** |

