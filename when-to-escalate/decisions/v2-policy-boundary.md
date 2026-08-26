# v2 Policy boundary — one-question lookahead, and why the theorem survives depth

The shipped analysis looks one question ahead and no further. This file states that
boundary precisely, records the substitution that would silently break it, and shows
that the impossibility result does not depend on it. Every number traces to
`results/voi-ceiling.json` or `results/entropy-baseline.json`; the notation is the
notation of `v2-definitions.md`.

> **Boundary statement.** The policy priced in this work is a one-question
> lookahead: it may ask at most one question, and after the answer arrives it
> **must act**. Formally it is `W_1` in the family defined in part 1, with
> `V_act` — not `V` — as the post-answer continuation, so the agent cannot ask
> again. This is a scope choice about the *policy*, not a premise of the
> *theorem*. The impossibility result rests on two facts that hold at every
> lookahead depth: the ceiling `V_act(b) − EC(ask | b) ≤ −2/13` holds at every
> belief in the simplex, and continuation costs are non-negative. On the
> unconstrained action menu, therefore, asking is never rational at any depth,
> and the margin widens with depth rather than closing.

---

## 1. The policy class

Let `A_q` be the answer set of question `q` and `b^u` the posterior after answer `u`.
Define the cost of acting under a budget of `k` remaining questions:

    W_0(b) = V_act(b)

    W_k(b) = min{ V_act(b),  EC(ask | b) + Σ_{u ∈ A_q} P_b(u) · W_{k−1}(b^u) }

`W_0` is "act now, best non-ask action." `W_k` is "act now, or spend one question and
face the same problem with one fewer left." The budget counts questions, not turns.

The shipped analysis is exactly `W_1`. Its continuation term is

    V_q(b) = Σ_u P_b(u) · V_act(b^u) = Σ_u P_b(u) · W_0(b^u)

and `VoI(q | b) = V_act(b) − [ EC(ask | b) + V_q(b) ]` is the amount by which the
`k = 1` ask branch beats `W_0(b)`. Naming the inner term `W_0` is what pins the depth
at one: `V_act(b^u)` is a terminal act, so there is no second question anywhere in the
object. Nothing else in the definition sets the depth, which is why the substitution in
part 2 changes the policy class without changing the shape of the formula.

---

## 2. The `V(b^u)` trap — two errors, and neither of them is depth

Writing `V(b^u)` in place of `V_act(b^u)` inside `V_q` looks like buying a second step
for free. It is wrong twice.

**First, it reproduces the `V`-versus-`V_act` tautology one level down.** `ask` is in
the menu, so `V(b^u) = min_{a ∈ F} EC(a | b^u) ≤ EC(ask | b^u)` **identically**. That
is the same defect recorded at `v2-definitions.md:129` for the prior-level baseline:
`ask` gets priced as a terminal action on one side of the comparison and as
ask-plus-the-next-action on the other. Moving it one level down does not fix it; it
hides it.

**Second, the resulting object is not `W_2`.** Compare the two continuations at `b^u`:

    W_2's:    min{ V_act(b^u),  EC(ask | b^u) + Σ_{u'} P_{b^u}(u') · W_0(b^{u,u'}) }
    V(b^u):   min{ V_act(b^u),  EC(ask | b^u) }

The difference is the entire missing term `Σ_{u'} P_{b^u}(u') · W_0(b^{u,u'}) ≥ 0`, so
`V(b^u) ≤ W_2(b^u)`. A genuine two-step policy charges the second question a
continuation as well. **`V(b^u)` implements a policy that believes the second
question's follow-up is free.** It is not a two-step policy and not a cheap
approximation to one — it is cheap in the wrong direction, because the under-pricing
sits entirely on the ask branch. It biases the comparison in favour of the action under
test, at exactly the point where the analysis exists to find out whether that action
pays. Name it that way rather than "a two-step policy," because "two-step" makes it
sound like an upgrade.

`W_2` is available and well defined, and it is a strictly harder object: it needs an
answer model for a second round of questions on the posteriors `b^{u,u'}`. Part 3 is
the reason it was not built.

---

## 3. Depth-independence — the theorem does not rest on the boundary

Two premises. Both are already committed; neither mentions a depth.

**Premise A — the ceiling holds at every belief.** On the unconstrained menu,

    V_act(b) − EC(ask | b) ≤ −2/13    for every belief b

`check_global_ceiling` in `experiments/voi_ceiling.py:374` computes the maximum over
*all* beliefs — the whole readiness simplex crossed with `b_h ∈ [0, 1]` — in exact
`Fraction` arithmetic, with the two monotonicity conditions `−ν < c_T − c_F < α`
asserted rather than assumed. The bound is attained, not merely argued: at the all-hot
vertex with `b_h = t* = 3/13`, `V_act = 30/13` and `EC(ask) = 32/13`, while `hold` and
`escalate_pause` cost `84/13` and `66/13` and so cannot lower the cap. A deliberately
dumb 60-step float grid reaches `−0.1667` and does not exceed the closed form's
`−0.153846`.

That it is a maximum over *all* beliefs and not over the 100 observed ones is what
makes it usable here. Posteriors are beliefs. `b^u`, `b^{u,u'}`, and every deeper node
of any lookahead tree are points of the same simplex, so premise A binds at every node
of the tree, not only at its root.

**Premise B — continuation costs are non-negative.** `W_k(b) ≥ 0` for every `k` and
`b`. Every entry of `costs.COST` is non-negative, so `W_0 = V_act ≥ 0`; and if
`W_{k−1} ≥ 0` then both branches of the `W_k` minimum are non-negative combinations of
non-negative numbers. Induction closes it.

Premise B is invariant 6. Gate 5 corrected invariant 6 down to a tautology: the
measured slack equals `V_q` to `7.77e-16`, so the invariant reduces to `V_q ≥ 0`,
which is free from the non-negativity of the matrix (X2). Being free is exactly why it
carries weight here. What made it worthless as an independent check is precisely what
makes it load-bearing: it follows from the cost matrix alone, with no reference to the
data, the answer model, the question set, or the depth. An invariant that cannot fail
tells you nothing about an implementation, and is the only kind of premise that can be
asserted at every node of an arbitrarily deep tree at once. A check that had to be
verified per node — as any data-dependent one would — could not be quantified over a
tree nobody enumerates. The check dismissed as trivial for validating the `k = 1` bound
is the load-bearing half of the depth result, and it is load-bearing *because* it is
trivial.

**The argument.** For every `k ≥ 1` and every belief `b`, on the unconstrained menu:

    EC(ask | b) + Σ_u P_b(u) · W_{k−1}(b^u)
        ≥ EC(ask | b)                            by premise B
        ≥ V_act(b) + 2/13                        by premise A
        > V_act(b)

So the ask branch is never the strict minimum, `W_k(b) = V_act(b)` for every `k`, and
the whole tree collapses to acting now. Asking is never rational on the unconstrained
action menu at any lookahead depth.

Three things read off the chain:

- **The margin does not narrow with depth.** Every term dropped is non-negative, so a
  deeper tree can only make the ask branch dearer. `2/13` is a floor on the gap, not an
  estimate of it.
- **A deeper no-ask baseline would widen it further.** `V_act(b)` is the cost of acting
  now. If some richer model made acting later cheaper, `V_act` would fall and the gap
  would grow. Depth is not a direction in which asking can be rescued.
- **It inherits the answer-model-freeness of the ceiling.** Neither premise refers to
  `P_b(u)`, to the Bayes update, or to the question set beyond requiring that answers
  have probabilities summing to one and that posteriors are beliefs. A wrong answer
  model, a different question set, or a second-round answer model on `b^{u,u'}` changes
  nothing in the chain.

**Attainment says depth provably cannot matter on some cases.** `V_q = 0` exactly on
16 of 400 case-question pairs on the published arm and 52 of 400 on the calibrated arm
(0 on raw, 12 on rebaselined). There the `k = 1` bound is reached rather than bounding:
the continuation is already zero, which is the lowest any depth could drive it. A free
perfect oracle still loses by the full `2/13`. On those pairs the deepest possible tree
and the shallowest agree exactly.

**What this settles.** `v2-definitions.md:259` says the ceiling shows "the horizon was
not the binding constraint." That was asserted from a `k = 1` computation, and a reader
was entitled to object that a one-step ceiling cannot speak for a two-step policy. The
chain above is the argument the sentence needed: the horizon is not the binding
constraint at any horizon. v1's myopia claim splits in two, and the halves go different
ways:

- **"A strict one-step rule does not price asking" — true, and it stays.** v1's policy
  compared `EC(ask | b) = 2 + 2·b_h` terminally against the other actions. That is not
  a price for a question, and v1 was right to name it a limitation.
- **"Asking is undervalued, and would earn its place if priced" — false here.** v2
  priced it properly and it still loses, by at least `2/13` per case, on the
  unconstrained menu, at every depth.

---

## 4. What this does not cover

**The constrained menu.** `no_direct_answer` removes `answer`, which removes the `α·t`
half of the cap and lifts the ceiling to `+1.0` at the all-hot vertex with `b_h = 0`;
it stays positive along the all-hot ray for `b_h < 1/5`, bound there by
`escalate_notify`. Premise A fails on that menu, so nothing above rules asking out
under that constraint, at any depth. In this dataset the positive region is empty, and
the two reasons are different and stay apart:

- For `calibrated` it is **unreachable by construction** — the isotonic map's reachable
  range begins at `6/23 ≈ 0.2609`, above both `t* = 3/13 ≈ 0.2308` and the region's
  `1/5 = 0.2`, so no calibrated belief can land in it at all.
- For `published`, `rebaselined`, and `raw` the region **is** reachable, and is empty
  only because no case that carries `no_direct_answer` lands in it: all 8 constrained
  cases are `a05-restricted` with `b_h ≥ 0.40`, since the archetype that forbids
  answering is the one where a human is likely needed.

**A cheaper question.** Premise A is a statement about the `ask` row `(2, 4)`. Scaling
that row by λ turns the ceiling positive at exactly `λ = 15/16`, i.e. `(15/8, 15/4)`, a
reduction of `1/16` = 6.25%. The general condition is `c_F/ν + c_T/α < 1`; this matrix
gives `32/30 = 16/15 > 1`. The result is contingent on a price, and it holds by a small
margin.

**Deferral is not in the model.** Every row of `costs.COST` prices the outcome of one
turn, `ask` included: its `(2, 4)` is described in `src/costs.py` as deferring a needed
handoff while keeping the lead alive, i.e. the delay price of spending the turn on a
question. No row prices a state transition. "Hold now, decide later" is therefore not
representable, and `W_k`'s terminal condition is a budget of questions, not a count of
turns. That is v1's turn-boundary limitation (`paper/main.tex:1060`), and nothing here
narrows or answers it.

**The scope of the claim.** This bounds the value of one more question inside a deeper
policy, at every depth, on this action menu and this cost matrix. It is not the claim
that no interaction design could justify asking. A design that changes the menu, the
price of a question, or what a single turn may contain is outside the premises — and
the constrained menu above is a worked example of a menu on which the argument does not
apply.

---

## 5. Where this lands

- `v2-definitions.md:154` states the implementation boundary (`V_act`, not `V`, inside
  `V_q`). `v2-definitions.md:259` states the horizon claim. Both carry a one-line
  pointer here.
- Paper, two edits, both Gate 7: a third beat in the theorem section after the theorem
  and the attainment sharpening, saying the margin does not close at any lookahead
  depth because the bound needs only non-negative continuation costs; and the retraction
  of the myopia framing in Limitations, where v1 made the claim — `main.tex:249`,
  `:343`, `:687`, `:947`, `:1050`. `:687` sits inside the `:683` band-claim debt (V2),
  so Gate 7 rewrites that line once, not twice.
- Recorded as Y1–Y5 in `v2-design-decisions.md`.
- No new code. Premise A is under test in the `voi_ceiling` suite; premise B is
  invariant 6 in `tests/test_entropy_baseline.py`. A `W_2` computation would exhibit
  depth 2 only, while the argument covers every depth, so it was not built.
