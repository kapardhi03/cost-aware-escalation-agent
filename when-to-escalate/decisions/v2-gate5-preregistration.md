# Gate 5 pre-registration — the entropy-threshold baseline, first VoI computation

**Status: locked before any Gate 5 number is computed.** This file lands in a commit
made while `experiments/entropy_baseline.py` and `results/entropy-baseline.json` do
not exist, so the baseline's rule, the arm set, the threshold grid, the unit of
comparison and the sign/magnitude boundary are fixed before the artifacts that
consume them, and the ordering is checkable in the git history.

Provenance for everything here: (AI-proposed), **confirmed** by Kaps in the Gate 5
opening exchange, except where marked otherwise.

---

## 1. What Gate 5 is for, and what this document can and cannot claim

Gate 5 owes three things carried to it explicitly:

1. The comparison against the "ask whenever `H(b)` exceeds a threshold" baseline
   named at `decisions/v2-definitions.md:76` — "a fair baseline rather than a
   strawman: it is the natural thing to do if you have entropy and no way to price
   it, and it is what the field's own habit of thresholding on uncertainty amounts
   to."
2. Invariant 8 from `v2-definitions.md:405`: identity `g`, empty `Q`, reproducing
   v1's decisions on all 100 cases — "or the comparison in Gate 5 is not measuring
   what it claims."
3. OQ3's naming discipline: the VoI honesty check is a **self-consistency** check of
   the implementation, everywhere it appears, and never a validation.

**The sign of this comparison is already committed data, and this document exists
mostly to stop the run from appearing to discover it.** Four facts were read from
committed artifacts during the Gate 5 opening exchange, before this file was
written:

- **All 400 per-case ceilings are negative**, in `results/voi-ceiling-arms.json` →
  `per_arm[arm].per_case[].ceiling`. Per arm the least negative values are
  `published` −0.400000, `rebaselined` −0.400000, `raw` −0.259819, `calibrated`
  −0.463970. So on every case of every arm, asking already costs more than the best
  non-ask action before any answer is priced.
- **The unconstrained-menu maximum is `−2/13` and the result is analytic**
  (`results/voi-ceiling.json`, T5). No belief set can move it, so no threshold on
  `H(b)` can find a case where asking pays.
- **v1 already published an unconditional ask baseline that loses**: `always_ask` on
  test, mean cost 2.84 against `cost_aware` 1.72, 21 missed escalations against 8
  (`results/run.json` → `summaries.test.policies`).
- **Gate 3 withdrew the IG ordering of the three questions.** 27 of 88 sweep
  variants flip it; `results/answer-model.md` withdraws "any claim that the IG
  ordering of these three questions means something."

So the pre-commitment here does **not** bind an unknown verdict. What it binds is
the unit the loss is reported in, the grid, the arm set, which tier of the result
rests on the answer model, and the requirement that the sign be presented as a
regression guard rather than a finding.

**Why this is not v1's `always_ask` again.** v1's baseline asks unconditionally and
prices `ask` as a *terminal* action, charging `C(ask, s)` and stopping. The Gate 5
baseline is the sophisticated version a reader would propose as the fix: it asks
only where the belief is uncertain, and it is priced as ask-**then-act**, so it pays
`EC(ask | b) + V_q(b)` and gets the benefit of the answer. Conditioning on
uncertainty and crediting the answer are exactly the two things that could have
rescued asking. Neither does, and Gate 5 measures by how much.

**What is genuinely new at this gate.** `V_q` and per-case `VoI` have never been
computed in this repository — `experiments/answer_model.py` computes information
gain, and its `voi_context()` only quotes Gate 1's ceiling. Gate 5 is therefore the
first gate that can test invariants 2, 4 and 6 of `v2-definitions.md:387` against
actual VoI values rather than against the analytic bound. That, the per-threshold
firing counts, and the cost magnitude are the new content.

**What Gate 5 does not do.** It does not touch `costs.COST`, does not re-run or
retune the Gate 3 sweep, does not rest any claim on the withdrawn IG ordering, does
not overwrite `results/run.json`, `results/voi-ceiling.json`,
`results/voi-ceiling-arms.json`, `results/abstention.json` or any Gate 2 or Gate 3
artifact, does not add a production `ask` feature, does not edit `paper/main.tex`,
and makes zero API calls.

---

## 2. The arms — locked

Four: `published`, `rebaselined`, `raw`, `calibrated`, the same set and the same
sources as `results/voi-ceiling-arms.json`. (Kaps-decided.) Gate 5 reads the
per-case ceilings from that artifact, which carries four arms, so matching it means
dropping no column rather than adding one.

**Recorded, because it differs from the sibling artifact.** Gate 4's abstention run
scored *three* arms and gave a reason: "rebaselined would add a column about cache
drift, which abstention has nothing to do with"
(`results/abstention.json` → `beliefs.why_three_arms_not_four`). That reason applies
with equal force here — entropy-thresholding has nothing to do with cache drift
either. Four arms is chosen anyway, for consistency with the artifact Gate 5 reads,
and the consequence is locked now rather than argued later: **the `rebaselined`
column carries no claim of its own.** It is a cache-drift column, it is labelled as
one in the artifact, and no Gate 5 or Gate 7 sentence may rest on it.

Claim split is `test`. Dev is where the isotonic map was fitted, so calibrated `b_h`
on dev is in-sample; dev is computed, shown, and labelled in-sample, and no claim
rests on it. Carried from T11 unchanged.

---

## 3. The baseline policy — locked

**The rule.** Ask iff `H_q(b) > τ`, where `H_q` is `H(b)` quantised to
`H_DECIMALS = 12`; otherwise take the `V_act` argmin. Strict inequality, so τ at the
top of the observed range fires on nothing and τ at the bottom fires on everything
except an exact tie at the minimum.

**The fallback is v1, and that is verified rather than assumed.** v1's `cost_aware`
takes the argmin over the full five-action menu including `ask`; invariant 7 is
committed as holding on 100/100 cases, `ask` never being the myopic argmin
(`results/voi-ceiling.json` → `invariants.ask_never_myopic_argmin`). So the `V_act`
argmin equals v1's decision on every case, and the baseline differs from v1 on
exactly the cases where it fires. That isolates the ask decision and nothing else.

**Tie-break.** v1's legacy rule, not Gate 4's safest-first rule. U6 established that
the two differ on exactly one case, `a11-repeated-097`, on dev only, and invariant 8
requires reproducing v1 on all 100 including that one. The legacy rule is used
throughout Gate 5 so the fallback and invariant 8 agree.

**Which question the baseline asks — the free oracle.** The baseline is handed the
question maximising `VoI(q | b)` on that case, over the Gate 3 question set `Q`.
This is deliberately the best case for the baseline and it is not realistic; it is
chosen because it needs no stable ordering and therefore does not rest on Gate 3's
withdrawn result. The claim it supports is "even given the cost-optimal question for
free, the entropy rule loses." (Kaps-decided.)

**The realistic variant is secondary and labelled.** `argmax_q IG(q | b)` — ask the
most informative question — is what the habit literally is, so it is computed and
reported, labelled **answer-model-dependent and ordering-fragile**, with a pointer
to the 27-of-88 flip count. It may not carry a headline. Locked: if the two variants
select different questions on some cases, that count is reported; it is a fact about
the tables, not evidence about either.

**`q_null` is excluded from the oracle's argmax.** It has `IG = 0` by construction
and asking it costs `EC(ask | b)` for nothing, so including it would let the oracle
pick a question that is strictly dominated and flatter the baseline in the one
direction that is not informative. It is retained in the reported table as the
zero-information reference.

---

## 4. What is scored, in which units, and which tier rests on what

**Units.** Bits select and bits trip: `H_q(b) > τ` compares bits to bits, and the
question argmax compares VoI to VoI or IG to IG. Cost points score. Nothing in the
implementation may compare a bit value to a cost value, per `v2-definitions.md:73`.

**The excess.** On a firing case the baseline pays `EC(ask | b) + V_q(b)` where the
cost-aware policy pays `V_act(b)`, so

    excess(b) = EC(ask | b) + V_q(b) − V_act(b) = −VoI(q* | b)

with `q*` the oracle's choice. Three tiers, reported separately and never merged:

| tier | quantity | rests on | role |
| --- | --- | --- | --- |
| 1 | `excess(b) ≥ EC(ask \| b) − V_act(b) = −ceiling(b)` | nothing beyond `costs.COST` and the belief | **headline** |
| 2 | `excess(b) = −max_q VoI(q \| b)`, expected cost | the Gate 3 answer model, no simulated answer | reported |
| 3 | realised cost after a simulated answer | the answer model *and* a simulated draw | self-consistency only, §8 |

Tier 1 is answer-model-free because `V_q(b) ≥ 0` — every entry of `costs.COST` is
non-negative — so the bound holds for **any** answer model, including a perfect
oracle. It is the same move Gate 3 made for the ceiling, and it inherits the same
robustness. Since the per-case ceilings are committed, tier 1's summands are
committed and only the index set — which cases fire at which τ — is new. That is
stated in the artifact so tier 1 reads as the regression guard it is.

`V_act(b)` is recoverable from the committed per-case rows without recomputation:
`V_act = ceiling + EC(ask | b)` and `EC(ask | b) = 2 + 2·b_h` exactly by invariant 5,
with `b_h` in the row. Locked: Gate 5 recomputes `V_act` from `costs.COST` and
asserts agreement with that recovery on all 400 pairs. A mismatch is a bug in the
new code, not a finding.

**The aggregate.** Per arm and per τ: number of cases firing, mean and total excess
at tier 1, the same at tier 2, and the resulting mean cost against v1's committed
`cost_aware` mean. Reported test-only for claims, dev shown and labelled.

---

## 5. The sign/magnitude boundary — the central pre-commitment

Locked, in these words:

- The **sign** of every excess is committed data. It follows from the 400 negative
  ceilings and from the analytic `−2/13` maximum, both of which predate this gate.
  Gate 5 reproduces it as a regression guard and says so in the artifact.
- The **magnitude** is the result: how many cases fire at each threshold, and
  what the habit costs in cost points on this data.
- No Gate 5 or Gate 7 sentence may describe the comparison as *establishing*,
  *confirming*, *showing* or *finding* that entropy-thresholding loses. It quantifies
  a loss whose sign is already proved.

The corollary, also locked: if the run produced a positive excess anywhere, that
would be a **bug** in the new code contradicting a committed invariant, not a
discovery. It is handled by raising, not by reporting.

---

## 6. The τ grid, and the S4 inventory

**Reused, not re-derived.** `experiments/abstention.py` already implements the
pre-registered grid: eleven deciles from 0% to 100% of the observed `H(b)`
distribution **on the arm being scored**, taken over all 100 cases of that arm, with
`H_DECIMALS = 12` quantisation and both the quantile and the absolute bit value
reported. Gate 5 imports `h_of`, `h_quantized`, `quantile` and `tau_grid` from it.
(Kaps-decided: import, do not lift into `src/`; a committed Gate 4 script is not
edited for tidiness.) Cross-experiment import is the established pattern —
`abstention.py` already imports `answer_model`, and `abstention.h_of` delegates to
`answer_model.joint_entropy`, so one entropy implementation serves all three gates.

Two properties of the grid are carried from Gate 4 rather than restated as new: a
decile grid on a tied distribution repeats values, and where two quantiles give the
same τ the rows are identical by construction; and the grid is taken over 100 cases
while scoring is on 50, so the top decile can fire on nothing.

The `rebaselined` arm needs a grid Gate 4 did not build. It is built with the same
function on the same definition. No new tunable.

**S4 inventory — every number in this gate that is stated in absolute units:**

| number | why it is absolute |
| --- | --- |
| `H_DECIMALS = 12` | derived at Gate 4 against the measured float-noise bound and the smallest genuine gap; carried unchanged, not re-chosen |
| `−2/13`, `3/13`, `1/5` | exact rationals derived from `costs.COST` by closed-form maximisation. Consequences of the matrix, with no scale to be a fraction of |
| agreement tolerance `1e-12` | resolves float noise on the `V_act` recovery check, not signal |
| the eleven deciles | quantiles by construction, which is the S4 treatment, not an exception to it |

**Zero new tunables at this gate.** τ is Gate 4's, quantised the same way, on the
same population definition. If a knob appears during implementation it is a §10
falsifier, not a detail.

---

## 7. Invariant 8 — locked

Setting `g` to the identity and `Q` to the empty set must reproduce v1's decisions
on all 100 cases. Locked as an assertion in code, not a reported number:

- With `Q = ∅` there is no question to ask, so the policy is the `V_act` argmin;
  with `g` the identity the beliefs are v1's committed beliefs.
- The action on every one of the 100 cases must equal
  `results/run.json` → `rows[].decisions.cost_aware.action`, and the test-split
  aggregate must equal the committed `summaries.test.policies.cost_aware`:
  mean cost 1.72, `answer` 15 / `escalate_notify` 20 / `hold` 15, 8 missed
  escalations, 0 constraint violations.
- A single disagreement raises. It would mean the Gate 5 policy object is not v1
  plus a question set, and the comparison would not be isolating the ask decision.

**The τ = 0th-decile anchor.** At the bottom of the grid the baseline fires on every
test case, which makes its ask component comparable to v1's committed `always_ask`
row. The two are *not* equal — v1 prices `ask` as terminal at total 142 / mean 2.84,
while Gate 5 prices it as ask-then-act and so must come out strictly higher on any
case where `V_q > 0`. Locked: the artifact reports both numbers side by side with
the reason they differ, and asserts the Gate 5 figure is not lower. Equality on
every case would mean `V_q` is identically zero, which is a bug.

**Invariants 2, 4 and 6, tested here for the first time.** Locked as assertions:

- Invariant 2: `V_act(b) − V_q(b) ≥ 0` on all 400 pairs. A violation is a bug in the
  answer model or the Bayes update, not a finding.
- Invariant 4: where the non-ask argmin is constant across all answers to `q`,
  `V_q(b) = V_act(b)` exactly, so `VoI(q | b) = −EC(ask | b)`. The count of pairs in
  this regime is reported, since it is unknown in advance and is the mechanism
  behind most of the loss.
- Invariant 6: `VoI(q | b) ≤ V_act(b) − EC(ask | b)` on all 400 pairs — the new
  computation against Gate 4's committed bound. This is the check that ties Gate 5
  to the analytic result, and it is the one worth the most.
- Invariant 3: `Σ_u P_b(u) · b^u(s) = P_b(s)` for every state, on every pair. The
  identity both proofs rest on.

---

## 8. The self-consistency check — naming locked

Tier 3 needs an answer the data does not contain. The cases are single messages, so
the answer must be simulated from the same `P(u | s)` that produced the prediction,
which makes the check a **self-consistency check of the implementation** and not
evidence that the answer model is right. Locked per OQ3's resolution:

- It is named a self-consistency check **everywhere it appears** — in the script, in
  the JSON key names, in the markdown artifact, and in any Gate 7 prose.
- The words *validation*, *validated*, *verified against reality* and *out-of-sample*
  may not attach to it.
- The absence of external validation is a Limitations entry at Gate 7, not a hedge
  inside a results paragraph. Gate 5 owes the naming; Gate 7 owes the entry.
- The `P(u | s)` sensitivity sweep from Gate 3 is the load-bearing defence and is
  cited as such rather than re-run.

The simulation is seeded and the seed is recorded in the artifact, so tier 3 is
reproducible. A seed is not a defence against the circularity and is not presented
as one.

---

## 9. What is computed, and where it lands

| artifact | status | contents |
| --- | --- | --- |
| `experiments/entropy_baseline.py` | new | the baseline policy, `V_q` and per-case VoI, four arms × the τ decile grid, the three tiers, invariants 2/3/4/6/8 |
| `results/entropy-baseline.json` / `.md` | new | per-arm per-τ firing counts and excess at tiers 1 and 2, the invariant-8 reproduction, the `always_ask` anchor, the tier-3 self-consistency check, the S4 inventory |
| `tests/test_entropy_baseline.py` | new | the invariants as tests, the sign guard, the naming sweep, negative controls on each |
| `results/voi-ceiling-arms.json` | **untouched** | read for per-case ceilings; the tier-1 bound must agree with it |
| `results/run.json` | **untouched** | read for v1's committed decisions and the `always_ask` row |
| `experiments/abstention.py` | **untouched** | imported for `h_of`, `h_quantized`, `quantile`, `tau_grid` |
| `costs.COST` | **untouched** | locked by OQ4's resolution |

The test suite is **654 passing** at this gate's open.

---

## 10. What would make this document false

Stated in advance, so the failure is recognisable rather than absorbable:

- An arm added or dropped after the numbers are seen, or a claim resting on the
  `rebaselined` column.
- τ redefined in absolute bits, or any new tunable introduced at this gate.
- The baseline's non-firing fallback differing from v1's decision on any case, or
  Gate 4's safest-first tie-break used anywhere in Gate 5.
- `q_null` included in the oracle's argmax, or the oracle variant swapped for the
  argmax-IG variant in a headline.
- Any claim resting on the IG ordering Gate 3 withdrew, or the argmax-IG variant
  reported without the ordering-fragility label.
- The comparison described as establishing, confirming, showing or finding that
  entropy-thresholding loses, in the artifact or in the paper.
- A positive excess reported rather than raised.
- The tier-1 bound presented as answer-model-dependent, or the tier-2 figure
  presented as answer-model-free.
- Invariant 8 relaxed to the test split, or asserted on aggregates rather than on
  all 100 per-case actions.
- The tier-3 check called a validation, or described as out-of-sample, anywhere.
- A dev number carrying a held-out claim.
- Any assignment into `costs.COST`, any edit to a committed Gate 1–4 artifact, any
  edit to `paper/main.tex`, or any API call during Gate 5.

---

## Provenance index, Gate 5 pre-registration

| # | Item | Provenance | Status |
| --- | --- | --- | --- |
| W1 | This document is not blind: the 400 negative ceilings, the analytic `−2/13`, v1's `always_ask` row and Gate 3's withdrawn ordering were all read before it was written, and are listed so no reader mistakes them for results | (AI-proposed) | **noted** |
| W2 | The sign is committed data and is reproduced as a regression guard; the magnitude — firing counts per threshold and cost per arm — is the result. No write-up may describe the comparison as establishing the sign | (Kaps-decided) | **confirmed** |
| W3 | Gate 5 is not v1's `always_ask` again: the baseline conditions on uncertainty and is priced as ask-then-act, so it gets both of the things that could have rescued asking | (AI-proposed) | **confirmed** |
| W4 | Four arms, matching `voi-ceiling-arms.json`. Gate 4's abstention chose three for a stated reason that applies here too, so the `rebaselined` column is locked as carrying no claim | (Kaps-decided) | **confirmed** |
| W5 | The baseline is handed the VoI-maximising question — the best case for it — because that needs no stable ordering and so does not rest on Gate 3's withdrawn result | (Kaps-decided) | **confirmed** |
| W6 | The argmax-IG variant is computed and reported as secondary, labelled answer-model-dependent and ordering-fragile, and may not carry a headline | (AI-proposed) | **confirmed** |
| W7 | `q_null` is excluded from the oracle's argmax and kept as the zero-information reference | (AI-proposed) | **confirmed** |
| W8 | Three tiers, never merged: the answer-model-free bound is the headline, the expected excess is reported, the realised figure is self-consistency only | (AI-proposed) | **confirmed** |
| W9 | Bits select and trip thresholds, cost points score; no bit value is compared to a cost value anywhere in the implementation | (Kaps-decided) | **confirmed** |
| W10 | τ is Gate 4's decile grid, imported rather than lifted into `src/`; zero new tunables, and the full absolute-number inventory is carried | (Kaps-decided) | **confirmed** |
| W11 | Invariant 8 is an assertion on all 100 per-case actions plus the committed test aggregate, on v1's legacy tie-break; a single disagreement raises | (Kaps-decided) | **confirmed** |
| W12 | Gate 5 computes `V_q` and per-case VoI for the first time, so invariants 2, 3, 4 and 6 are tested against actual VoI values rather than against the bound; invariant 6 is the check that ties the new code to the analytic result | (AI-proposed) | **confirmed** |
| W13 | The tier-3 check is named a self-consistency check of the implementation everywhere it appears; the Limitations entry is Gate 7's, and the seed is recorded without being offered as a defence | (Kaps-decided) | **confirmed** |
| W14 | Gate 5 makes zero API calls, adds no production `ask` feature, and modifies no committed Gate 1–4 artifact and no `.tex` | (AI-proposed) | **noted** |
