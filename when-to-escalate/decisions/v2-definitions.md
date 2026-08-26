# v2 Definitions — entropy, information gain, value of information, calibration loss

Every symbol is stated in the cost notation v1 already uses, so each one maps onto
something that exists in `src/costs.py` or `src/belief.py`. Where a number is
computed rather than defined, it traces to `results/voi-ceiling.json`.

---

## 0. Notation carried forward from v1

| Symbol | Meaning | Where it lives in v1 |
| --- | --- | --- |
| `r ∈ R = {hot, warm, cold}` | buying readiness | `costs.READINESS_LABELS` |
| `h ∈ {False, True}` | a human is genuinely needed | `costs.State.needs_human` |
| `s = (r, h)` | the hidden state, six of them | `costs.State` |
| `b = (b_r, b_h)` | the two-part belief | `belief.Belief` |
| `P_b(s)` | `b_r(r) · b_h` or `b_r(r) · (1 − b_h)` | `costs.state_probability` |
| `C(a, s)` | cost of action `a` in state `s` | `costs.COST` |
| `EC(a \| b) = Σ_s P_b(s) C(a, s)` | expected cost of one action | `costs.expected_cost` |
| `F` | the feasible action set after constraints | `costs.feasible_actions` |
| `π(b) = argmin_{a ∈ F} EC(a \| b)` | the myopic policy | `costs.choose_action` |

One new symbol does all the work in v2:

    V(b) = min_{a ∈ F} EC(a | b)

**the value of a belief** — the cost the policy expects to pay if it has to act
now, under this belief. `π(b)` is the action; `V(b)` is the number. v1 computed
`V(b)` on every case and threw it away, keeping only the argmin. Every definition
below is built out of `V`.

Two scoping rules, stated here so nothing downstream can quietly break them.

- All of `V`, `IG` and `VoI` are computed under the **calibrated** belief, with
  `b_h = g(z)` for the raw score `z` and the calibration map `g` fitted in Gate 2.
  Never under raw `z`. This is the order the scope statement commits to:
  calibrate first, price questions on top of the fixed belief.
- `EC(ask | b)` is not obviously a new parameter. `ask` already has a row in
  `costs.COST`, and because that row is flat in readiness (2 when `h=False`, 4
  when `h=True`) it collapses to

        EC(ask | b) = 2 + 2·b_h                    (verified on 100/100 cases)

  The price of a question is fixed by the practitioner matrix v1 already locked,
  and it depends only on `b_h`. Whether v2 may reuse that row as the price of
  asking turns out to be the central open question — see OQ4.

---

## 1. Entropy

The belief has two parts, so it has two entropies. Both in **bits** (log base 2),
so that "one bit" means "one clean yes/no answer's worth" and the paper never has
to translate.

    H_r(b) = − Σ_{r ∈ R} b_r(r) · log₂ b_r(r)                   range [0, log₂3] = [0, 1.585]

    H_h(b) = − b_h·log₂ b_h − (1 − b_h)·log₂(1 − b_h)            range [0, 1]

For the joint six-state distribution, `readiness` and `needs_human` are
independent by design (locked decision 0a), so the joint entropy is **exactly**
the sum:

    H(b) = H_r(b) + H_h(b)                                       range [0, 2.585]

That additivity is a consequence of the independence the two-part belief was
built on, not a convenience. It means "which part am I uncertain about" is a
well-posed question with an exact decomposition rather than an attribution guess —
a single collapsed confidence score could not answer it. Worth stating in the
paper as a second dividend of the two-part belief, alongside the one v1 already
claimed (being able to express "hot AND needs a human").

**Entropy is not cost.** `H(b)` is in bits; `V(b)` is in cost points. Nothing in
the policy may compare them. Uncertainty becomes actionable only once it is
converted into cost points, which is precisely the job of VoI. This is also why
the "ask whenever `H(b)` exceeds a threshold" policy in Gate 5 is a fair
baseline rather than a strawman: it is the natural thing to do if you have
entropy and no way to price it, and it is what the field's own habit of
thresholding on uncertainty amounts to.

---

## 2. Expected information gain of a question

A question `q` drawn from the question set `Q` (enumerated in Gate 3) has a
finite answer set `A_q`. The **answer model** supplies a likelihood `P(u | s)`:
how likely answer `u` is in each hidden state. That likelihood is the one genuinely
new modelling object in v2, and Gate 3 exists to ground it and to write down every
assumption behind it.

Predictive probability of hearing `u`, under the current belief:

    P_b(u) = Σ_s P_b(s) · P(u | s)

Posterior belief after hearing `u`:

    b^u(s) = P_b(s) · P(u | s) / P_b(u)          for P_b(u) > 0

Expected information gain, in bits:

    IG(q | b) = H(b) − Σ_{u ∈ A_q} P_b(u) · H(b^u)

Entropy now, minus the entropy we expect to be left with. It is the mutual
information between the hidden state and the answer.

**Sign.** `IG(q | b) ≥ 0` always, with equality exactly when `P(u | s)` is the
same for every `s` — a question whose answer does not depend on the hidden state.
A *particular* answer can raise entropy: `H(b^u) > H(b)` is ordinary and happens
whenever a surprising answer drags a confident belief toward the middle. The
*average* cannot, because conditioning never increases expected entropy. So
questions do not sort into "helps" and "hurts". They sort into **"cuts a lot"**
and **"cuts almost nothing"**, and the near-zero bucket is where the interesting
failure is.

**A problem this definition creates, which the code has to answer.** `b^u` is a
distribution over the six joint states and it **need not factorise**. Any answer
that carries information about both readiness and needs-human couples them, and
the coupled posterior cannot be stored in a `Belief` (a readiness dict plus a
scalar). See open question OQ1.

---

## 3. Value of information

`IG` is in bits and the policy pays in cost points, so `IG` cannot enter the
decision rule. VoI is the conversion: not "how much sharper would the belief
get", but "how much cheaper would the decision get".

### The baseline `ask` is measured against — `V`, not `V_act`, is a trap

The first form I wrote was

    VoI(q | b) = V(b) − V_q(b) − EC(ask | b)              ← WRONG, see below

and it is wrong in a way worth recording, because it looks right. `ask` is in the
action menu, so `V(b) = min_{a ∈ F} EC(a | b) ≤ EC(ask | b)` **identically**.
Since `V_q(b) ≥ 0` (every cost in the matrix is non-negative), that form gives
`VoI ≤ 0` for *any* matrix, *any* belief and *any* question — a tautology dressed
as a finding. The double-count is that `V(b)` already prices `ask` as a terminal
action, while the ask branch prices it as ask-plus-the-next-action.

The fix is to measure the ask branch against the best action that is **not** ask:

    V_act(b) = min_{a ∈ F \ {ask}} EC(a | b)

    V_q(b)   = Σ_{u ∈ A_q} P_b(u) · V_act(b^u)

    VoI(q | b) = V_act(b) − [ EC(ask | b) + V_q(b) ]

Read left to right: what the best immediate action costs, minus what asking costs
plus what we expect to pay acting on the answer. `ask` is worth it when this is
positive, and the question posed is `argmax_{q ∈ Q} VoI(q | b)`.

Note `V_act` and not `V` inside `V_q` too. After the answer the agent **must
act** — it may not ask again. That is what makes this one-question lookahead
rather than sequential planning, and it is the carried-forward boundary Gate 6
has to state. Using `V(b^u)` there would quietly turn this into a two-step policy.

Stated as a boundary, with the substitution's two errors, in `v2-policy-boundary.md`.

### Two properties, both of which become assertions in code

**`V_act(b) − V_q(b) ≥ 0`, always** — the information itself, before paying for
it, is never harmful. `EC(a | b)` is linear in the joint probability vector, so
`V_act(b)` is a minimum of linear functions and therefore concave. The posteriors
average back to the prior: `Σ_u P_b(u)·b^u(s) = Σ_u P_b(s)·P(u | s) = P_b(s)`.
Jensen on a concave function gives `Σ_u P_b(u)·V_act(b^u) ≤ V_act(b)`. This is
worth more as a test than as a sentence in the paper: a violation is proof of a
bug in the answer model or the Bayes update, and it should fail loudly.

**`VoI(q | b)` can be negative, and usually will be.** Asking pays only when the
belief is uncertain enough *and* the cost gap between actions is wide enough that
a changed belief changes the action by more than `2 + 2·b_h`.

### The headline statement

Suppose `argmin_{a ∈ F \ {ask}} EC(a | b^u)` is the same action `a*` for every
answer `u` with `P_b(u) > 0`. Then

    V_q(b) = Σ_u P_b(u)·EC(a* | b^u) = EC(a* | b) = V_act(b)

using the same posterior-averaging identity, so `VoI(q | b) = −EC(ask | b) < 0`
exactly.

**If the answer would not change the action, the question is worth exactly
nothing — however many bits it carries.** `IG` large and `VoI` exactly
`−EC(ask | b)` is not an edge case; it follows from the definition. That is the
"high information gain, low value of information" bucket the design record
predicted, now with a proof rather than an intuition.

### An answer-model-free ceiling, and what it says about this matrix

Because `V_q(b) ≥ 0`, VoI is capped without knowing anything about the answer
model at all:

    VoI(q | b) ≤ V_act(b) − EC(ask | b)

This grants a free perfect oracle — an answer so good that the post-answer
decision costs nothing. Every number below comes from
`experiments/voi_ceiling.py`, offline and deterministic, output committed at
`results/voi-ceiling.json`:

```bash
python3 experiments/voi_ceiling.py --json results/voi-ceiling.json
```

- **On the 100 committed cases** (`results/run.json` beliefs, `costs.COST`, each
  case's hard constraints applied): the ceiling is negative on **100/100**. Least
  negative `−0.400`, attained by **11** cases at `V_act = 2.0`, `EC(ask) = 2.4`,
  `b_h = 0.2`; most negative `−3.500`. The anchor case `a02-deep-018` sits at
  `−0.500` (`V_act = 2.100` via `escalate_notify`, `EC(ask) = 2.600`).
- **Over every belief that exists**, not just these 100, and in closed form
  rather than by grid search: the maximum is exactly **`−2/13 = −0.153846`**,
  attained at `b_r = (hot 1, warm 0, cold 0)`, `b_h = 3/13`.

So under this cost matrix and this accounting, `VoI(q | b) < 0` for every belief,
every question and every answer model. **Asking can never be justified, and no
information calculation can change that.** The reason is a price mismatch, not
myopia: the most the policy can ever expect to pay by acting immediately is
`max_b V_act(b) = 30/13 = 2.3077`, while the cheapest a question can ever be is
`min_b EC(ask | b) = 2` — and the two do not occur at the same belief, leaving a
`2/13` gap that information cannot cover.

**The closed form.** Write `α = C(answer, (·, True)) = 10` for a false assertion
and `ν = C(escalate_notify, (·, False)) = 3` for a needless escalation. Both rows
are flat in readiness, and so is `ask`, so with `t = b_h`:

    V_act(b) ≤ min(α·t, ν·(1 − t))              readiness cannot raise this cap
    u(t)     = min(α·t, ν·(1 − t)) − EC(ask | t)

`u` rises on `t ≤ t*` and falls on `t ≥ t*`, so

    max_b [ V_act(b) − EC(ask | b) ] = u(t*),   t* = ν/(α + ν) = 3/13
                                     = α·ν/(α + ν) − EC(ask | t*)
                                     = 30/13 − 32/13 = −2/13

`t*` is not a new constant: it is the `answer`-versus-`escalate_notify` crossover
already derived below, so the belief where asking comes closest to paying for
itself is exactly the belief where the policy is most torn between speaking and
escalating. That is the right place for it to be, which is a small piece of
evidence that the derivation is describing the matrix rather than an artifact.

The bound is **attained**, not merely a bound: at `b_h = 3/13` on the all-hot
vertex, `hold = 84/13` and `escalate_pause = 66/13` both exceed the cap `30/13`,
so `V_act` equals the cap there. The script constructs that witness, evaluates it
through `src/costs.py`'s own `expected_cost` rather than through its own
arithmetic, and agrees to `1e−9`. An independent 60-per-axis grid search returns
`−0.166667`, below the closed form and short by `0.0128` because `3/13` is not on
a `1/60` grid — the direction that would signal a bug (grid *exceeding* the
closed form) does not occur.

Two monotonicity conditions make `t*` the maximiser: `−ν < c_T − c_F < α`, i.e.
`−3 < 2 < 10`. The script asserts both rather than assuming them, so the closed
form fails loudly if the matrix is ever changed out from under it.

This is consistent with, and a stronger reading of, what v1 already observed:
`ask` is chosen 0 times in 100 cases (`results/run.json` action census —
`escalate_notify` 43, `answer` 30, `hold` 27). v1 attributed that to the one-step
horizon. The ceiling says the horizon was not the binding constraint. The script
also confirms `V_act == V` on **100/100** — `ask` is never even the myopic argmin,
which is the same fact read off the arithmetic instead of off the census.

The horizon claim is proven for every depth in `v2-policy-boundary.md`, part 3.

**The one place the impossibility is not unconditional.** `no_direct_answer`
removes `answer` from the non-ask menu, which removes the `α·t` half of the cap
and can only raise `V_act`. On that menu the ceiling **does** go positive: up to
`+1.000` at the all-hot vertex with `b_h = 0`, and positive along the all-hot ray
for `b_h < 1/5`, bound by `escalate_notify`. Asking beats a needless escalation
when a lead is hot, a human probably is not needed, and answering is forbidden —
which is a sensible thing for a policy to want to do. But **none of the 8 cases
that carry the constraint lands in that region**: all eight are `a05-restricted`,
and every one has `b_h ≥ 0.40`, because the archetype that forbids answering is
the one where a human is likely needed. The two conditions are anti-correlated by
construction. So the empirical claim (0/100) holds for a verified reason, and the
theoretical claim has to be stated as: unconditional on the unconstrained menu,
and empirically vacuous rather than impossible under `no_direct_answer`. Both
belong in the paper; collapsing them into one sentence would overclaim.

**How close it is.** Scaling the `ask` row uniformly by λ, the ceiling turns
positive at exactly **λ = 15/16 = 0.9375**, i.e. `ask` priced at `(15/8, 15/4) =
(1.875, 3.750)` instead of `(2, 4)`. A reduction of exactly `1/16` — **6.25%**,
not the ~6.3% first estimated by grid search. A numeric bisection agrees to
`1e−9`. The practitioner set the price of a question just barely above what the
decision is worth. That near-miss is what makes this interesting rather than a
dead end, and it is a sensitivity worth reporting whatever we decide.

**The general condition**, which is the part worth carrying into the paper,
because it does not depend on these particular five numbers. With `ask` priced at
`(c_F, c_T)`, the ceiling can be positive iff

    α·c_F + ν·c_T < α·ν        ⟺        c_F/ν + c_T/α < 1

Read it directly: the price of a question measured against a needless escalation
when no human is needed, plus its price measured against a false assertion when
one is, must sum to under 1. v1 sits at `2/3 + 4/10 = 16/15 ≈ 1.0667`, and
`λ* = 1/(16/15) = 15/16` is just the reciprocal. This turns a fact about our
matrix into a testable condition on anyone's.

**This finding is conditional on the accounting choice** — see OQ4, resolved
below.

### Relationship to `Decision.margin`, which already exists

`Decision.margin` is the gap to the next-best feasible action. A wide margin
makes an argmin flip less likely, so margin is a cheap **screen** for "VoI is
probably at its floor here" and can order which cases to compute VoI on first. It
is a heuristic, not a bound: nothing above bounds VoI by the margin, and the
write-up must not imply it does. The `V_act(b) − EC(ask | b)` ceiling *is* a real
bound, and it is just as cheap, so prefer it as the screen.

### Where the escalation threshold comes from

For `answer` against `escalate_notify`: `EC(answer | b) = 10·b_h` and
`EC(escalate_notify | b) = 3·(1 − b_h)`. They cross at `13·b_h = 3`, i.e.
`b_h = 3/13 ≈ 0.2308`. Both are flat in readiness, so this threshold is exact and
readiness-free — which is why v1's escalation behaviour is a pure function of
`b_h`, and why recalibrating `b_h` is the lever Gate 2 pulls.

---

## 4. Cross-entropy and KL as the recalibration loss

The calibration map is a monotone `g: [0,1] → [0,1]` applied to the raw
needs-human score. For case `i`, raw score `z_i`, calibrated belief
`b_h⁽ⁱ⁾ = g(z_i)`, label `y_i ∈ {0,1}` from `data/cases.json`.

Cross-entropy (log loss), in bits:

    CE(g) = −(1/N) · Σ_i [ y_i·log₂ g(z_i) + (1 − y_i)·log₂(1 − g(z_i)) ]

**Why this and not ECE alone.** ECE bins, and binning eight distinct score values
with as few as four cases in a bin is doing almost no work — a bin of `n = 4`
cannot be distinguished from noise by any reliability diagram. CE is per-case,
needs no bins, and is a proper scoring rule, so it cannot be improved by a map
that merely reshuffles cases between bins. It is also the right thing to *fit*
against, which matters because Gate 2 has to choose a map, not only measure one.
ECE stays in the report because v1 reported it and the comparison has to be
like-for-like.

**KL is the same quantity, so report it as a decomposition and not as second
evidence.** Group the cases by score value (the grid has eight of them). For group
`j` with `n_j` cases and observed positive rate `ŷ_j`:

    CE(g) = Σ_j (n_j/N) · H(ŷ_j)  +  Σ_j (n_j/N) · KL( Bern(ŷ_j) ‖ Bern(g(z_j)) )
            └────── irreducible ──────┘   └────────── miscalibration ──────────┘

The first term is the conditional label entropy: the loss that remains when the
map is perfect, because cases sharing a score genuinely disagree on the label. No
calibration map can remove it. The second term is what `g` can actually fix, and
it is zero exactly when `g(z_j) = ŷ_j` for every group.

This gives Gate 2 the number it needs to be honest with: **a floor.** "CE fell
from A to B" means little on its own; "CE fell from A to B against an irreducible
floor of ϕ" says how much of the available improvement was taken. Quoting CE and
KL side by side as if they were independent findings would be double-counting, and
this is the kind of thing a referee catches.

**Caveat, stated now rather than discovered later.** The decomposition is exact
only where "group by score" is well defined, i.e. on the discrete 0.1 grid. Once
the logprob scores are continuous there are no ties, grouping needs binning again,
and the floor becomes an estimate with the bin width as a free choice. So compute
the floor on the grid, where it is exact, and carry it as the reference. The grid
gives a clean floor and no near-coin-flip cases; the continuous scores give
near-coin-flip cases and a fuzzier floor. Both are needed, for different jobs.

**Metric budget.** CE (fit and report), ECE (report, for the v1 comparison),
reliability diagram (report, via the existing `paper/figures/make_figures.py`).
Brier was used in the Gate 0 probes; recommend it does **not** enter the paper —
it measures the same thing as CE less usefully, and a fourth calibration number
buys nothing but the appearance of rigour.

---

## 5. Units

Three units are in play and every formula in the paper should carry its own.

| Quantity | Unit | Range |
| --- | --- | --- |
| `H_r`, `H_h`, `H`, `IG` | bits | `[0, 1.585]`, `[0, 1]`, `[0, 2.585]`, `[0, H(b)]` |
| `V`, `V_act`, `EC`, `VoI` | cost points | `V ≤ V_act ≤ 30/13 = 2.3077`; `EC(ask) ∈ [2, 4]` |
| `CE` | bits per case | `≥` the irreducible floor |
| `ECE` | unitless (a probability gap) | `[0, 1]` |

The only legitimate bridge from bits to cost points is VoI. Any other comparison
between the two columns is a category error.

---

## 6. Invariants worth asserting in code

Written down here so Gate 4 implements against them rather than discovering them.

1. `IG(q | b) ≥ 0`, and `= 0` iff `P(u | s)` is constant in `s`.
2. `V_act(b) − V_q(b) ≥ 0`. A violation is a bug in the answer model or the Bayes
   update, not a finding.
3. `Σ_u P_b(u) · b^u(s) = P_b(s)` for every `s` — posteriors average to the prior.
   This is the identity both proofs rest on, so it is the first thing to test.
4. If the non-ask argmin is constant across answers then `V_q(b) = V_act(b)`, so
   `VoI = −EC(ask | b)` exactly.
5. `EC(ask | b) = 2 + 2·b_h` exactly, independent of `b_r`. Verified: holds on
   100/100 committed cases (`voi_ceiling.py`, `invariants.ec_ask_is_affine_in_b_h`).
6. `VoI(q | b) ≤ V_act(b) − EC(ask | b)`, with no reference to the answer model.
7. `V_act(b) ≥ V(b)`, with equality iff `ask` is not the myopic argmin. Verified:
   `V_act ≥ V` on 100/100 and equality on 100/100 (`voi_ceiling.py`,
   `invariants.v_act_at_least_v` and `.ask_never_myopic_argmin`), consistent with
   the 0 asks in the action census.
8. Setting `g` to the identity and `Q` to the empty set must reproduce v1's
   decisions on all 100 cases. v2 has to contain v1 as a special case, or the
   comparison in Gate 5 is not measuring what it claims.
9. `answer`, `escalate_notify` and `ask` are flat in readiness. The closed-form
   ceiling depends on it, so `voi_ceiling.py` raises rather than averaging if a
   future matrix edit breaks it — and the two monotonicity side conditions
   `−ν < c_T − c_F < α` are asserted for the same reason.

---

## 7. Open questions — three resolved, one held

The analysis under each question is left as written. The **Resolution** lines are
the decisions taken on it, so the reasoning that produced them stays readable
alongside the outcome.

**OQ1 — the posterior does not fit in a `Belief`.** `b^u` is a joint over six
states and need not factorise into (readiness distribution, scalar). Options: (a)
restrict `Q` to questions whose likelihood factorises, keeping `Belief` unchanged;
(b) widen the posterior representation to a six-vector used only inside the VoI
computation, with `Belief` left exactly as it is for the policy interface.
**Recommend (b).** It costs one adapter next to `expected_cost`, keeps `Belief`
and all 337 tests untouched, and does not let the representation quietly censor
the question set. (a) would mean the answer model is shaped by a storage
convenience, which is the wrong thing to let happen at Gate 3.

> **Resolution (Kaps-decided, confirmed): (b).** The internal posterior widens to
> a six-vector over `readiness × needs_human`, used only inside the VoI
> computation. `Belief` and its interface are untouched, so the policy signature,
> the cache format and the 337 tests are unaffected. Gate 3 owes an adapter and a
> test that the six-vector reduces to a `Belief` whenever the posterior does in
> fact factorise.

**OQ2 — abstention introduces a free parameter, and the paper's selling point is
that it does not have any.** The design record wants: high `H(b)` and
non-positive VoI implies `escalate_pause`. But if the matrix already prefers
`answer` on such a case, overriding it *is* a new rule with a new threshold on
`H(b)`, and adding a free parameter to a policy whose whole claim is that the
cost matrix decides needs to be argued for, not slipped in. Options: (a) accept
the threshold and defend it explicitly, sweeping it as a sensitivity; (b) reframe
abstention as a **fallback ordering** rather than an override — when `ask` loses
only because `VoI ≤ 0`, resolve the fallback toward `escalate_pause` instead of
`escalate_notify`; (c) keep abstention as a reported diagnostic and leave the
policy alone.

Note the ceiling result damages (b): if `VoI ≤ 0` on every case, then "ask lost
only because VoI ≤ 0" is true everywhere, so (b) stops being a narrow tie-break
and becomes a blanket rewrite of the fallback — which is a large behavioural
change wearing the costume of a small one. **Recommend (a) if OQ4 resolves toward
re-pricing, (c) otherwise.** Needs your call, after OQ4.

> **Resolution: held (noted).** Deliberately not decided at Gate 1. OQ4 resolved
> to (C)-primary, which by the recommendation above points at (c) — abstention as
> a reported diagnostic, policy untouched — but the call is deferred to Gate 4,
> where the abstention wiring is actually built and the cost of each option is
> visible rather than predicted.

**OQ3 — the VoI honesty check cannot be an external validation, and Gate 5 must
not describe it as one.** Checking predicted VoI against realised cost reduction
needs the answer actually received. The cases are single messages; there are no
real answers. So the check can only simulate the answer from the same `P(u | s)`
that produced the prediction, which makes it a **self-consistency** check of the
implementation, not evidence that the answer model is right. Genuine validation
would need a second turn per case, which is new data. Recommend: run it, name it
self-consistency, and put the gap in Limitations. Sensitivity analysis over
`P(u | s)` (already planned for Gate 3) is the real defence — if VoI swings wildly
under small likelihood changes, that is the finding.

> **Resolution (Kaps-decided, confirmed): as recommended.** The check runs, is
> named a self-consistency check of the implementation everywhere it appears, and
> the absence of external validation goes into Limitations as a new entry rather
> than a hedge inside Results. The `P(u | s)` sensitivity sweep from Gate 3 is the
> load-bearing defence and is reported as such.

**OQ4 — does `C(ask, s)` price the friction of asking, or the harm of deferring?
This is now the decision the rest of v2 hinges on, and it has to be settled before
Gate 3.** The additive form charges `EC(ask | b)` *and then* `V_q(b)`, so
`C(ask, s)` has to mean the incremental friction only — one extra turn, the risk of
looking robotic. But read the matrix's own comment on `ask` at `(hot, True)`:
`4  defers a needed handoff, but keeps the lead alive`. That is the *deferral harm*,
which `V_q(b)` then prices a second time. v1's `ask` row is a blended practitioner
judgment covering both things, and it cannot be split arithmetically — under
`h=False`, `hold` on a hot lead costs 6 while `ask` costs 2, so the row is not
"deferral plus friction", it is a distinct judgment about a question keeping the
lead engaged.

Three coherent ways out.

- **(A) Additive, reusing the v1 row as friction.** No new parameters, fully
  continuous with v1, and it is what the ceiling above computes. Cost: it
  double-counts deferral, and the honest conclusion is that `ask` is unreachable —
  VoI `< 0` for every belief and every answer model.
- **(B) Additive, with a new practitioner-set friction row.** `ask`'s price becomes
  pure friction and the deferral harm comes from `V_q(b)` alone. This is the only
  route on which `ask` can actually fire. Cost: one new cost row, i.e. a genuinely
  new free parameter — defensible as a practitioner judgment of the same kind as
  the other 30 numbers, but it must be declared, and the break-even at
  `λ = 15/16` means the result will be sensitive to it. Any friction row below
  `(1.875, 3.750)` produces asks; above it, none. That is uncomfortably tight
  and the paper has to say so.
- **(C) Report the impossibility as the result and do not rescue `ask`.** Keep the
  v1 matrix untouched; the contribution is the ceiling itself, plus the sensitivity
  showing how far the price must fall. The claim becomes: *under a
  practitioner-set matrix where a question costs 2–4 and the whole decision is
  worth at most 30/13, no value-of-information calculation can justify asking on
  the unconstrained action menu, and the horizon was never the binding
  constraint.* Cost: `ask` never fires, so Gates 4 and 5 change shape — three
  policies still run, but VoI's contribution is a proof and a sensitivity rather
  than a behaviour change.

**Recommend (C) as the primary result with (B) run as a declared sensitivity.**
(C) is a sharper and more surprising paper than "we priced VoI and `ask` fired on
six cases", it needs no new parameters, it is provable on committed data, and it
directly corrects v1's own stated reading of why `ask` never fires. (B) alongside
it answers the obvious referee question — "so what would it take?" — without the
paper having to pretend the re-priced matrix is the real one. (A) alone is (C)
without the sensitivity.

> **Resolution (Kaps-decided, confirmed): (C) primary, (B) as a declared
> sensitivity, and (A) is explicitly not a route.** The cost matrix is not
> touched — that would reopen a locked v1 decision and read as goalpost-moving.
> The λ re-pricing is computed on a local copy of the matrix inside
> `voi_ceiling.py` and never written back to `costs.COST`; the script contains no
> assignment into `COST` at all.
>
> Two wording constraints follow from the constrained-regime result above and are
> binding on Gates 5–7. First, the impossibility claim must carry **"on the
> unconstrained action menu"** — under `no_direct_answer` the ceiling reaches
> `+1.000` and the positive region is `b_h < 1/5` on the all-hot ray. Second, the
> reason 0/100 still holds is empirical, not logical: all 8 constrained cases have
> `b_h ≥ 0.40`, so the region exists but is unreached. The paper states both.
>
> A note on labels: the instruction referred to the cost-matrix route as (A). In
> this draft (A) is the no-new-parameters route that reuses the v1 row, and (B) is
> the one that adds a friction row. The intent — do not touch the matrix, report
> the impossibility, price the sensitivity — is unambiguous and matches the
> recommendation, so nothing in the work changes; recorded here so the labels are
> not read back inverted later.

This changes the scope sentence in the design record. It currently says v2 exists
to price the payoff that the myopic policy undervalues. The Gate 1 analysis says
pricing the payoff is not sufficient, because the payoff is capped at `30/13` and
the price floor is `2`, and the two do not meet. That is a **changed** premise and
needs a provenance row.

---

## 8. Still parked

The two logprob-cache questions — token scheme and coverage — belong at the top of
Gate 2, immediately before any scoring run. Not asked here because Gate 1 writes
no code and generates no data.
