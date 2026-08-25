# Gate 3 pre-registration — the question set and the answer model

**Status: locked before any information-gain number is computed.** This file and the
tables it locks (`src/questions.py`) land in one commit, made while
`experiments/answer_model.py` and `results/answer-model.json` do not exist — so no
`IG` had been computed when the tables were fixed, and that is checkable in the git
history rather than asserted here. The answer model is the one object in v2 that
could be tuned after seeing results — nudge a likelihood and the information gain
moves — so every choice is fixed first and changing it afterwards is a diff.

The rules are not only prose. The question set, the likelihood form and the sweep
grid are module constants in `src/questions.py`, and `tests/test_questions.py`
asserts this document and those constants agree, the same link Gate 2 used to keep
its pre-registration from going stale silently.

Provenance for everything in this file: (AI-proposed), **confirmed** by Kaps in
the Gate 3 opening exchange, except where marked otherwise.

---

## 1. What Gate 3 is for, and what it is not for

Gate 1 §2 defines expected information gain over a question set `Q` and an answer
model `P(u | s)`, and defers both: "`Q` (enumerated in Gate 3)" and "That likelihood
is the one genuinely new modelling object in v2, and Gate 3 exists to ground it and
to write down every assumption behind it." Neither existed in code before this gate
— no `Q`, no answer set, no likelihood over states appeared anywhere in `src/`,
`experiments/` or `data/`; the only greppable near-misses were the word "questions"
inside two prompt strings and the log-likelihood in Platt scaling, neither of which
is a question set. Gate 3 builds them.

**What Gate 3 does not do: defend the impossibility result.** Gate 1 §3 proves

    VoI(q | b) ≤ V_act(b) − EC(ask | b)

which follows from `V_q(b) ≥ 0` alone. The bound grants a free perfect oracle — an
answer so informative that the post-answer decision costs nothing — so it holds for
**every** question and **every** answer model, and its maximum over all beliefs is
`−2/13` in closed form. Nothing in this file can move that number. A likelihood
sweep cannot defend a bound that already assumed the best possible likelihood.

This corrects OQ3's Gate 1 resolution, which called the sweep "the load-bearing
defence" of the result. That was written before the answer-model-free ceiling was
proved, and it is wrong as stated: **the impossibility is answer-model-free and
needs no defence from this gate.** The correction is recorded in the design record
rather than by editing OQ3 in place, per the no-retroactive-edits rule.

What the sweep does measure is stated in §5: whether the **information-gain
magnitudes** are stable under perturbation of the likelihoods — the mechanism, not
the claim.

So the honest description of this gate: it makes the theorem's "every answer model"
quantifier concrete by exhibiting a worked instance, and it discharges the adapter
OQ1 owes. It is an illustration with its assumptions written down, and it is
labelled that way everywhere it appears.

---

## 2. The question set `Q` — locked

**Selection rule, fixed before any information-gain number is computed
(Kaps-decided):** questions are drawn from what the 11 archetypes in
`data/cases.json` actually leave ambiguous. Not from what would make `ask` fire.
The ordering matters and is recorded here: the archetypes were tabulated first,
the ambiguity in each was read off its label distribution, and the questions were
written from that table — before any `IG` was evaluated.

The table the questions were drawn from, computed from `data/cases.json`:

| # | archetype | n | readiness | needs_human | what is ambiguous |
| ---: | --- | ---: | --- | --- | --- |
| 1 | template opener | 10 | all cold | all False | nothing — no split on either axis |
| 2 | send photos | 8 | all warm | 4 / 4 | needs_human only |
| 3 | one-word ping | 8 | 4 cold, 4 warm | 4 / 4 | both axes |
| 4 | ready buyer | 16 | all hot | 8 / 8 | needs_human only |
| 5 | legal / land papers | 12 | 4 hot, 8 warm | 8 True / 4 False | both; 8 carry `no_direct_answer` |
| 6 | suspects a bot | 8 | 5 warm, 3 cold | 6 True / 2 False | both |
| 7 | competitor fishing | 8 | all cold | 4 / 4 | needs_human only |
| 8 | media, no text | 8 | 4 warm, 4 cold | all False | readiness only |
| 9 | over-sharer | 6 | 3 hot, 3 warm | all False | readiness only |
| 10 | polite time-waster | 10 | 6 warm, 4 cold | 6 False / 4 True | both |
| 11 | vulgar / off-topic | 6 | all cold | 2 False / 4 True | needs_human only |

Three axes of ambiguity appear: readiness-only (8, 9), needs_human-only (2, 4, 7,
11), and both (3, 5, 6, 10). `Q` has one question per axis, plus a control:

| id | question | answers `A_q` | targets |
| --- | --- | --- | --- |
| `q_timeline` | asks when they intend to decide | `soon`, `later`, `no_answer` | readiness |
| `q_authority` | asks whether anyone else signs off | `self`, `others`, `no_answer` | needs_human |
| `q_specifics` | asks for the one concrete detail the request turns on | `concrete`, `vague`, `no_answer` | both |
| `q_null` | a question whose answer cannot depend on the state | `a`, `b` | nothing — control |

`q_null` is in `Q` on purpose. Gate 1 §2 states `IG = 0` exactly when `P(u | s)` is
the same for every `s`; `q_null` is that case, so it is a live assertion that the
implementation reproduces the equality rather than a claim in prose.

**Three questions plus a control is the whole set, and it is not extended after
seeing results.** Adding a question later is adding a free parameter after the
fact. If a fifth is ever wanted, it goes in a new pre-registration.

The exact wording of each question is fixed in `src/questions.py` as a module
constant. Wording does not enter any computation — only `A_q` and `P(u | s)` do —
so it is recorded for readability, not as a knob.

---

## 3. The answer model `P(u | s)` — form locked

**Form (locked): a per-question table over the six states, every row summing to 1.**
Not learned, not fitted to the cases, not derived from a model. There are no
answers in the data to fit to — the cases are single messages, which is the same
fact that makes OQ3's check a self-consistency check.

Two structural assumptions, both stated here because both are contestable:

- **A1 — conditional independence of the answer from the message given the state.**
  `P(u | s)` does not depend on which case is being asked about, only on the hidden
  state. This is what makes one table serve all 100 cases. It is false in detail:
  a hot lead asked for a timeline in archetype 4 does not answer like a hot lead in
  archetype 9. Accepted because the alternative is 11 tables set by the same
  judgment with 11× the free parameters and no data to constrain any of them.
- **A2 — `no_answer` is a real answer, not missing data.** Every question carries a
  `no_answer` outcome with non-zero probability in every state, because a lead who
  ignores a question is common and the silence is itself informative. It also keeps
  every `P_b(u) > 0`, so the posterior in Gate 1 §2 is defined for every answer.

**The 54 numeric entries: (AI-proposed, Kaps-reviewed).** They are drafted by
Claude to express the ambiguity §2's table records, then reviewed by Kaps, who
overwrites any that read wrong. They are **not** practitioner-set and are described
that way nowhere. Labelling a Claude-drafted table "practitioner judgment" would
fabricate the provenance the rest of this record depends on, and the answer model is
illustrative anyway — the impossibility is answer-model-free (§1), so hand-crafting
54 practitioner probabilities for an illustration would be effort spent in the wrong
place (Kaps-decided).

What makes them locked rather than tunable is the commit ordering, not this
paragraph: they live in `src/questions.py`, committed **in the same commit as this
file** and **before `experiments/answer_model.py` exists**. That is the mechanism
Gate 2 used — its rules were constants in `src/calibrate.py`, committed before the
run — so "fixed before any information gain was seen" is a checkable property of the
git history. Changing an entry after that commit requires a new pre-registration
entry recording the change and the reason (§7).

Three structural choices in the entries, all visible in the tables:

- `q_timeline` is keyed on readiness alone and `q_authority` on needs_human alone,
  so their rows repeat across the other axis. That is what makes their posteriors
  factorise, and it is by construction rather than by luck.
- `q_specifics` is keyed on both axes, and its entries are **not** a product of a
  readiness factor and a needs_human factor. Verified exactly: `separates()` returns
  `False` for it, first witness at answer `concrete`, readiness pair `hot`/`warm`.
  This is the case that makes the §4 adapter necessary rather than decorative.
- Entries are stored as integers out of 100, so every row sums to exactly 1 and the
  separability test above runs in exact `Fraction` arithmetic rather than against a
  tolerance. `experiments/voi_ceiling.py` sets the same precedent.

**"54 entries" is the table size, not the count of independent judgments.** The
three tables hold 54 numbers, but the axis-only questions repeat rows across the
other axis and every row is constrained to sum to 1, so the free parameters are 22:

| question | table entries | distinct rows | free parameters |
| --- | ---: | ---: | ---: |
| `q_timeline` | 18 | 3 | 6 |
| `q_authority` | 18 | 2 | 4 |
| `q_specifics` | 18 | 6 | 12 |
| total | 54 | — | 22 |

Twenty-two is the number that matters for how tunable this model is, and it is the
number the §5 sweep perturbs.

**What this model is not.** It is not validated. Nothing in the data can confirm
these numbers are the right ones. That is stated in Limitations, and it is why the
gate's output is labelled an illustration.

---

## 4. The six-vector posterior and the factorisation test — owed by OQ1

OQ1's resolution (Kaps-decided, confirmed) chose option (b): the internal posterior
widens to a six-vector over `readiness × needs_human`, used only inside the VoI
computation, with `Belief` untouched. Gate 3 owes "an adapter and a test that the
six-vector reduces to a `Belief` whenever the posterior does in fact factorise."

Locked here:

- `Belief` is not modified. Its fields stay `readiness` and `needs_human`; the
  cache format and the policy signature are unchanged. Verified by the existing
  474 tests continuing to pass.
- The six-vector is indexed by `costs.READINESS_LABELS × (False, True)` in that
  order, matching `costs.state_probability`, so the widened object and the existing
  cost code agree on what state `i` means.
- The adapter goes one way by construction: `Belief → six-vector` is always exact.
  `six-vector → Belief` is defined **only** when the joint factorises, and raises
  otherwise rather than silently projecting. A projection that quietly discards the
  coupling would make a coupled posterior look storable, which is the exact error
  OQ1 exists to prevent.
- **The factorisation test asserts both directions**: that a factorising posterior
  round-trips to within 1e-12, and that a deliberately coupled posterior raises.
  A test that only checks the happy path would pass on an adapter that always
  projects.

`q_authority` and `q_timeline` are single-axis by construction, so their posteriors
factorise. `q_specifics` targets both axes, and its table is verified **not**
separable in exact arithmetic — no factorisation into a readiness term times a
needs_human term exists, first witness at answer `concrete` on the `hot`/`warm`
pair. It is the case that makes the adapter necessary rather than decorative.

A non-separable table does not by itself guarantee a coupled posterior on every
case: a belief with a zero entry can drop the rank back. So which of the 100 cases
actually produce a coupled posterior is a measured outcome, reported either way.

---

## 5. The sweep — locked, and labelled for what it measures

**Grid (locked):** each non-`no_answer` entry of each table is perturbed by
`±0.05` and `±0.10` in turn, rows renormalised, one entry at a time — a
one-at-a-time local sensitivity, not a joint sweep. Perturbations that would drive
an entry outside `[0.01, 0.99]` are clipped to that interval, and the clipping is
reported alongside the result rather than hidden.

**What is reported, and in these words:** the stability of the **information-gain
magnitudes** under perturbation of the likelihoods, and whether the ordering of
questions by `IG` survives. That is a statement about the mechanism.

**What is not claimed:** that this defends the impossibility result. §1 gives the
reason. The report and every downstream mention say so explicitly.

**Pre-registered reading of the outcome, so it cannot be narrated after the fact:**

- If the `IG` ordering of the three real questions is unchanged across every
  perturbation, the mechanism is locally stable and the illustration is not an
  artifact of the exact entries chosen.
- If the ordering flips under a `±0.05` perturbation, the answer model is too
  fragile to illustrate anything, and that is the finding — reported as such, with
  the illustration withdrawn rather than repaired by choosing better entries.

Both outcomes are publishable here. Neither changes any claim about `ask`.

---

## 6. What is computed, and where it lands

Offline and deterministic. **No API calls at any point in Gate 3** — the answer
model is a committed table, and the beliefs come from `results/run.json`. A gate
that makes no calls has nothing to cache and nothing to reproduce from.

| output | contents |
| --- | --- |
| `src/questions.py` | `Q`, the tables, the sweep grid, the adapter, as constants and functions |
| `experiments/answer_model.py` | computes `IG` per question per case, runs the sweep |
| `results/answer-model.json` | per-case `IG`, the sweep, the factorisation outcomes |
| `results/answer-model.md` | the rendered report, labelled an illustration |
| `tests/test_questions.py` | the prose-matches-constants link, the factorisation test both ways |

Invariants asserted in code, from Gate 1 §2 and §6:

1. `IG(q | b) ≥ 0` for every question and every one of the 100 beliefs.
2. `IG(q_null | b) = 0` to within 1e-12 for every belief — the equality case.
3. `Σ_u P_b(u) = 1` for every question and belief.
4. Every table row sums to 1 to within 1e-12.
5. `IG(q | b) ≤ H(b)` — a question cannot remove more entropy than is present.

**One free check worth stating in advance.** Four of the 100 cases have `b_h` at
exactly 0.0 — `a08-reaction-075`, `a08-reaction-077`, `a11-first-095`,
`a11-repeated-097`; none sits at 1.0 — so `H_h(b) = 0` on those four and no answer
can reduce it. One of them, `a11-repeated-097`, additionally has a degenerate
readiness belief `cold = 1.0`, giving `H(b) = 0` on **both** axes, so invariant 5
forces `IG = 0` for **every** question on that case. It is a check the data hands
over for free, and it fails loudly if the entropy code has a sign or normalisation
error. Source: `results/run.json`, `rows[*].belief`.

---

## 7. What would make this document false

Stated in advance, so the failure is recognisable rather than absorbable:

- A question added to `Q` after the numbers are seen.
- A table entry changed after the numbers are seen, without a new pre-registration
  entry recording the change and the reason.
- `experiments/answer_model.py` existing in any commit that does not already
  contain the filled tables in `src/questions.py` — that ordering is what §3
  substitutes for numbers this file does not carry.
- A Claude-drafted table described anywhere as practitioner judgment.
- The sweep reported as evidence for or against the impossibility result.
- The adapter projecting a coupled posterior instead of raising.
- Any of the five invariants asserted in prose here but not in code.
- Any API call made during Gate 3.

---

## Provenance index, Gate 3 pre-registration

| # | Item | Provenance | Status |
| --- | --- | --- | --- |
| P1 | Gate 3 is minimal and labelled an illustration; it does not defend the impossibility | (Kaps-decided) | **confirmed** |
| P2 | OQ3's "load-bearing defence" line is wrong; the impossibility is answer-model-free. Corrected in the design record, OQ3 left as written | (AI-proposed) | **changed** |
| P3 | `Q` is drawn from archetype ambiguity, tabulated before any `IG` is computed; nothing chosen to make `ask` fire | (Kaps-decided) | **confirmed** |
| P4 | `Q` is three questions plus the `q_null` control, and is not extended after results | (AI-proposed) | **confirmed** |
| P5 | `P(u \| s)` form locked as a per-question table over six states; A1 and A2 stated as contestable assumptions | (AI-proposed) | **noted** |
| P5a | The 54 table entries are drafted by Claude and reviewed by Kaps, never described as practitioner-set. Locked by commit ordering: they land in `src/questions.py` in this same commit, before `answer_model.py` exists | (AI-proposed, Kaps-reviewed) | **confirmed** |
| P6 | Six-vector posterior per OQ1(b); `Belief` untouched; the reverse adapter raises on a coupled posterior rather than projecting | (Kaps-decided) | **confirmed** |
| P7 | The sweep is ±0.05/±0.10 one-at-a-time, reported as IG-magnitude stability, with both outcomes pre-registered | (AI-proposed) | **confirmed** |
| P8 | Gate 3 makes zero API calls | (AI-proposed) | **noted** |
