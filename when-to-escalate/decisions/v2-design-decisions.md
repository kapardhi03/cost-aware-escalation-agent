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

What remains genuinely open at Gate 8 is therefore one technical item: the
`.gitignore` line 32 versus line 38 conflict, which may prevent the paper's
figure from being committed.

| # | Resolution | Provenance | Status |
| --- | --- | --- | --- |
| G9 | `build-log.md` rows 1/45/47 keep their cohort wording; an append-only log is not edited to match a later naming rule | (Kaps-decided) | **confirmed** |
| G10 | The 11 v1 commit messages are not rewritten; history integrity beats word-scrubbing and the words identify nothing | (Kaps-decided) | **confirmed** |
| G11 | `v1.0.0` is tagged retroactively at Gate 8, before `v2.0.0` | (Kaps-decided) | **noted** |

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
