# v2 Design Decisions

Planning notes for v2. Each entry tagged by who proposed it and its status.

## Scope

- Recalibrate the "needs_human" belief first, then compute Value of Information(VoI) on
  top of the fixed belief. VoI is only meaningful if the belief it is computed
  under is honest, so calibration comes first.
- Carried from v1: the one-step myopic policy undervalues the `ask` action,
  because asking pays off through a better belief next turn, not through lower
  cost this step. v2 exists to price that payoff.

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