#!/usr/bin/env python3
"""
entropy_baseline.py — what thresholding on entropy costs, and the first VoI numbers.

Two things, and the order matters.

**The sign is not measured here.** `results/voi-ceiling.json` proves
`VoI(q | b) <= V_act(b) - EC(ask | b)` with a closed-form maximum of `-2/13`, and
`results/voi-ceiling-arms.json` carries 400 per-case ceilings, every one negative.
Asking already costs more than the best non-ask action before any answer is priced.
Nothing below can move that, and this script reproduces it as a **regression guard**
against the committed artifact rather than as a finding. If any excess here came out
negative it would be a bug contradicting a committed invariant, and it raises.

**The magnitude is what this gate owes.** The baseline is the sophisticated version
of the habit: ask only where the belief is uncertain, and pay ask-then-act so the
answer is credited. Conditioning on uncertainty and crediting the answer are the two
things that could have rescued asking. Neither does, and the cost of trying is
measured per threshold and per arm.

The reason this is not v1's `always_ask` again. That policy asks unconditionally and
prices `ask` as **terminal** — it charges `C(ask, s)` and stops, for a committed test
total of 142. This one is conditional and charges `C(ask, s) + C(a_u, s)`, so at the
bottom of the threshold grid, where it fires on everything, it must come out strictly
dearer than 142 on any case where the follow-up action costs anything. That
comparison is asserted, not assumed.

What is genuinely new. `V_q` and per-case `VoI` are computed nowhere else in this
repository: `answer_model.py` computes information gain, and its `voi_context()` only
quotes the ceiling. So this is the first place invariants 2, 3, 4 and 6 of
`decisions/v2-definitions.md` section 6 can be evaluated on actual VoI values.

What invariant 6 turned out to be worth, since the pre-registration overrated it.
Substituting `VoI = V_act - EC_ask - V_q` into its slack `(V_act - EC_ask) - VoI`
cancels both other terms and leaves `V_q`, measured here as agreeing to within 8e-16.
So on these definitions the invariant reduces to `V_q >= 0`, which holds because
every entry of `costs.COST` is non-negative. It confirms the implementation is
self-consistent and it is not independent evidence for the bound. The independent
check is `ceiling_agreement`, which compares the recomputed `EC(ask | b) - V_act(b)`
against the committed per-case ceilings and recovers `V_act` a second way through
`ceiling + EC(ask | b)`.

What the same computation did establish, which was not pre-registered because it was
not anticipated: on 16 of the 400 published pairs `V_q = 0` exactly, so the ceiling is
**attained** rather than merely bounding. A free perfect oracle driving the
post-answer expected cost to zero still loses by the full `-ceiling`. The bound's
negativity therefore cannot be attributed to slack in the bound.

One thing the pre-registration did not anticipate, recorded because it changes the
code rather than the numbers. `V_q(b) = sum_u P_b(u) * V_act(b^u)` needs the expected
cost of an action under a **posterior**, and `src.questions.narrow` refuses to turn a
coupled posterior into a `Belief` by design — `q_specifics` on `a01-first-001`
answering "concrete" is a committed example of one that raises. So
`costs.expected_cost`, which takes the factorised two-part belief, cannot be used on
posteriors at all. This file adds `ec_joint`, the six-vector form, and asserts it
agrees with `costs.expected_cost` on all 100 priors across all five actions, where
both are defined. That is the cost-side counterpart of the entropy-side adapter OQ1
bought, and it is an adapter over the same representation, not a second cost model.

Units. Bits select and bits trip thresholds; cost points score. `H(b) > tau` compares
bits to bits and the question argmax compares VoI to VoI. No bit value is ever
compared to a cost value, per `decisions/v2-definitions.md:73`.

Two ledgers, kept apart. Tiers 1 and 2 are **expected** cost under the belief. The
realised ledger scores against the labels, which is the currency v1's committed 86
test points is in. An expected excess added to a realised total would be neither, so
they are reported separately and never summed.

Offline and deterministic. **No API calls.** Beliefs come from the four committed
arms, the answer model is a committed table, and the one sampling step is seeded.

Usage
    python experiments/entropy_baseline.py
    python experiments/entropy_baseline.py --json results/entropy-baseline.json \
                                           --md results/entropy-baseline.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ABSTENTION = ROOT / "experiments" / "abstention.py"
CEILING_ARMS_JSON = ROOT / "results" / "voi-ceiling-arms.json"
RUN_JSON = ROOT / "results" / "run.json"
REBASELINE_JSON = ROOT / "results" / "rebaseline.json"

#: Where each arm's committed v1-policy test score lives in rebaseline.json. The
#: tau = 1.0 row of every sweep fires on nothing, so it plays v1's fallback on all 50
#: cases and has to reproduce the entry for *its own* arm. Published's 86 is not the
#: reference for the other three: v1's policy on rebuilt beliefs scores 70 on raw and
#: 75 on calibrated, both committed in Gate 2. Comparing every arm against 86 would
#: report an excess against a total that arm never had.
COMMITTED_FALLBACK = {
    "published": ("published", "test"),
    "rebaselined": ("arms", "rebaselined_written"),
    "raw": ("arms", "fresh_raw"),
    "calibrated": ("arms", "fresh_calibrated"),
}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: `abstention` first, and its `vc`/`am` are reused rather than loaded again. It puts
#: ROOT on sys.path and already holds one instance of each experiment module, so
#: taking its handles guarantees a single `src.costs` and therefore one cost matrix.
#: Loading them separately would give two, which is the hazard `abstention` names.
ab = _load("abstention", ABSTENTION)
vc = ab.vc
am = ab.am

import src.costs as costs                                          # noqa: E402
from src.belief import Belief                                      # noqa: E402
from src.questions import (QUESTIONS, STATES, factorises,          # noqa: E402
                           widen)

#: Four, matching `results/voi-ceiling-arms.json` so no column is dropped. Gate 4's
#: abstention run scored three and gave a reason — "rebaselined would add a column
#: about cache drift, which abstention has nothing to do with" — that applies here
#: too. The consequence is locked instead: `rebaselined` carries no claim of its own.
ARMS = ("published", "rebaselined", "raw", "calibrated")

#: Held-out. Dev is where the isotonic map was fitted, so calibrated `b_h` on dev is
#: in-sample; dev is computed, shown and labelled, and carries no claim.
CLAIM_SPLIT = "test"

#: v1's ACTIONS-order rule, not Gate 4's safest-first rule. Invariant 8 requires
#: reproducing v1's decisions on all 100 cases including `a11-repeated-097`, the one
#: case where the two rules disagree, so the legacy rule is used throughout.
LEGACY_TIE_BREAK = True

QUANTILES = ab.QUANTILES
H_DECIMALS = ab.H_DECIMALS

#: The three real questions. `q_null` has IG identically 0, so an oracle allowed to
#: pick it could choose a strictly dominated question — full ask price, no
#: information — and flatter the baseline in the only direction that is not
#: informative. It stays in the reported table as the zero-information reference.
ORACLE_CANDIDATES = tuple(q for q in QUESTIONS if q.id != "q_null")

TOL = 1e-12

#: Float slack for agreement against committed 6dp artifact values.
ARTIFACT_TOL = 1e-6

#: Recorded so the sampling step reproduces. A seed is not a defence against the
#: circularity in section 8 and is not offered as one.
SEED = 20260826
N_DRAWS = 2000


class BaselineError(RuntimeError):
    """A precondition failed. Never downgraded to a warning."""


# --------------------------------------------------------------------------- #
# 1. The cost-side adapter: expected cost of an action under a six-vector
# --------------------------------------------------------------------------- #

def ec_joint(action: str, joint, matrix=None) -> float:
    """`EC(a | joint)` over the six states, for a joint that need not factorise.

    `costs.expected_cost` reads `belief.readiness` and `belief.needs_human` and
    multiplies them, so it is defined only where the joint is a product. Posteriors
    are not: `narrow` raises on them rather than projecting, precisely so the
    coupling stays visible. This is the same expectation written against the joint
    directly, and `adapter_agreement` checks the two coincide wherever both apply.
    """
    matrix = matrix if matrix is not None else costs.COST
    if action not in matrix:
        raise BaselineError(f"unknown action {action!r}")
    row = matrix[action]
    return sum(joint[s] * row[s] for s in STATES)


def adapter_agreement(rows: list[dict]) -> dict:
    """`ec_joint` against `costs.expected_cost` on every prior and every action.

    The priors factorise by construction, so this is where the two forms must agree
    exactly. Checked on all five actions rather than the three the policy ends up
    using, since the argmin is taken over a menu and a wrong entry anywhere moves it.
    """
    worst = 0.0
    worst_at = None
    for row in rows:
        b = Belief.from_dict(row["belief"])
        joint = widen(b.readiness, b.needs_human)
        for action in costs.ACTIONS:
            delta = abs(ec_joint(action, joint) - costs.expected_cost(action, b))
            if delta > worst:
                worst, worst_at = delta, (row["case_id"], action)
    if worst > TOL:
        raise BaselineError(
            f"ec_joint disagrees with costs.expected_cost by {worst:g} at "
            f"{worst_at}, above the {TOL:g} tolerance. The six-vector form is not "
            "the same expectation as the two-part form.")
    return {
        "what_it_checks": (
            "The six-vector expected cost equals the two-part expected cost on "
            "every prior and every action, so it is an adapter over the same cost "
            "model rather than a second one."),
        "n_comparisons": len(rows) * len(costs.ACTIONS),
        "max_abs_delta": worst,
        "within_tol": worst <= TOL,
        "why_it_is_needed": (
            "src.questions.narrow raises NonFactorisingError on a coupled posterior "
            "rather than projecting onto its marginals, so costs.expected_cost "
            "cannot be evaluated on one at all. q_specifics produces coupled "
            "posteriors on real cases (results/answer-model.json adapter."
            "coupled_example)."),
    }


# --------------------------------------------------------------------------- #
# 2. V_act, V, and the argmin
# --------------------------------------------------------------------------- #

def _rank() -> dict:
    order = costs.ACTIONS if LEGACY_TIE_BREAK else costs.tie_break_order()
    return {a: i for i, a in enumerate(order)}


RANK = _rank()


def non_ask_menu(constraints) -> tuple[str, ...]:
    """`F \\ {ask}` — the feasible actions with `ask` removed.

    Constraints are case-level facts about what the agent may do, so they survive an
    answer: the same menu applies at the prior and at every posterior. An answer to
    `q_authority` does not make `answer` available on a case that forbids it.
    """
    menu = tuple(a for a in costs.feasible_actions(constraints) if a != "ask")
    if not menu:
        raise BaselineError(f"constraints {list(constraints)} leave no non-ask action")
    return menu


def v_act(joint, constraints) -> tuple[float, str]:
    """`V_act(b) = min over F \\ {ask} of EC(a | b)`, and its argmin.

    The value is what `V_q` sums; the argmin is what invariant 4 watches and what the
    baseline plays when it does not fire.
    """
    menu = non_ask_menu(constraints)
    ecs = {a: ec_joint(a, joint) for a in menu}
    best = min(menu, key=lambda a: (ecs[a], RANK[a]))
    return ecs[best], best


def v_full(joint, constraints) -> tuple[float, str]:
    """`V(b)` — the same minimum with `ask` left on the menu. v1's rule."""
    menu = costs.feasible_actions(constraints)
    ecs = {a: ec_joint(a, joint) for a in menu}
    best = min(menu, key=lambda a: (ecs[a], RANK[a]))
    return ecs[best], best


# --------------------------------------------------------------------------- #
# 3. The first VoI computation
# --------------------------------------------------------------------------- #

def posteriors_for(question, joint, table=None) -> list[tuple[str, float, dict]]:
    """`(u, P_b(u), b^u)` for each answer, skipping answers of zero probability.

    Same arithmetic as `answer_model.evaluate`, which does not return the posteriors
    it builds. Rather than edit a committed Gate 3 script to expose them, they are
    rebuilt here and `question_voi` cross-checks the IG that falls out against
    `evaluate`'s committed implementation — so the duplication is verified, not
    trusted.
    """
    tab = question.table if table is None else table
    out = []
    for j, u in enumerate(question.answers):
        weights = {s: joint[s] * tab[s][j] / 100.0 for s in STATES}
        p_u = sum(weights.values())
        if p_u <= 0.0:
            continue
        out.append((u, p_u, {s: weights[s] / p_u for s in STATES}))
    return out


def question_voi(question, joint, constraints) -> dict:
    """`VoI(q | b) = V_act(b) - [EC(ask | b) + V_q(b)]`, with `V_q` over posteriors.

    `V_act` and not `V` inside `V_q`: the agent gets one question, so it cannot ask
    again after the answer. Relaxing that is Gate 6's boundary, not this gate's.

    The wrong form, `V(b) - V_q(b) - EC(ask | b)`, is a tautology here because
    `V(b) <= EC(ask | b)` identically once `ask` is on the menu. It is not computed.
    """
    prior_v_act, prior_argmin = v_act(joint, constraints)
    ec_ask = ec_joint("ask", joint)

    branches = posteriors_for(question, joint)
    v_q = 0.0
    argmins, coupled = {}, 0
    for u, p_u, post in branches:
        val, arg = v_act(post, constraints)
        v_q += p_u * val
        argmins[u] = arg
        if not factorises(post, tol=TOL):
            coupled += 1

    voi = prior_v_act - (ec_ask + v_q)
    constant_argmin = len(set(argmins.values())) == 1

    # Invariant 3, on this question's branches: posteriors average back to the prior.
    averaged = {s: sum(p_u * post[s] for _u, p_u, post in branches) for s in STATES}
    invariant_3 = max(abs(averaged[s] - joint[s]) for s in STATES)

    return {
        "question": question.id,
        "v_act": prior_v_act,
        "v_act_argmin": prior_argmin,
        "ec_ask": ec_ask,
        "v_q": v_q,
        "voi": voi,
        "ig": am.joint_entropy(joint) - sum(
            p_u * am.joint_entropy(post) for _u, p_u, post in branches),
        "n_answers": len(branches),
        "n_coupled_posteriors": coupled,
        # Keyed by answer, not by position: an answer with zero predictive
        # probability has no posterior and no branch, so a positional list would
        # silently shift every later entry.
        "posterior_argmin_by_answer": argmins,
        "argmin_constant_across_answers": constant_argmin,
        "invariant_2_slack": prior_v_act - v_q,
        "invariant_3_residual": invariant_3,
        "invariant_6_slack": (prior_v_act - ec_ask) - voi,
        # Invariant 4: a constant argmin forces V_q == V_act exactly, because
        # EC(a | b) is linear in the belief and the posteriors average to the prior.
        "invariant_4_residual": (abs(v_q - prior_v_act) if constant_argmin else None),
    }


# --------------------------------------------------------------------------- #
# 4. Per case, per arm
# --------------------------------------------------------------------------- #

def per_case(rows: list[dict]) -> list[dict]:
    """Every case of one arm: the fallback, the oracle's pick, and both excesses."""
    out = []
    for row in rows:
        b = Belief.from_dict(row["belief"])
        joint = widen(b.readiness, b.needs_human)
        constraints = tuple(row.get("constraints") or ())

        prior_v_act, prior_argmin = v_act(joint, constraints)
        prior_v, v1_action = v_full(joint, constraints)
        ec_ask = ec_joint("ask", joint)

        by_q = {q.id: question_voi(q, joint, constraints) for q in QUESTIONS}
        oracle = max(ORACLE_CANDIDATES, key=lambda q: by_q[q.id]["voi"])
        by_ig = max(ORACLE_CANDIDATES, key=lambda q: by_q[q.id]["ig"])

        out.append({
            "case_id": row["case_id"],
            "split": row["split"],
            "constraints": list(constraints),
            "b_h": float(row["belief"]["needs_human"]),
            "h_bits": ab.h_quantized(row),
            "labels": dict(row["labels"]),
            "v_act": prior_v_act,
            "v_act_argmin": prior_argmin,
            "v_full": prior_v,
            "v1_action": v1_action,
            "ec_ask": ec_ask,
            # Tier 1: answer-model-free, since V_q >= 0 for any answer model.
            "tier1_excess": ec_ask - prior_v_act,
            "oracle_question": oracle.id,
            "oracle_voi": by_q[oracle.id]["voi"],
            "tier2_excess": -by_q[oracle.id]["voi"],
            "argmax_ig_question": by_ig.id,
            "argmax_ig_voi": by_q[by_ig.id]["voi"],
            "oracle_and_ig_agree": oracle.id == by_ig.id,
            "by_question": by_q,
        })
    return out


# --------------------------------------------------------------------------- #
# 5. The regression guard against the committed ceilings
# --------------------------------------------------------------------------- #

def ceiling_agreement(arm: str, cases: list[dict], committed: dict) -> dict:
    """Tier 1 against `voi-ceiling-arms.json`, case by case.

    `tier1_excess = EC(ask | b) - V_act(b) = -ceiling(b)`, so this is the check that
    the new code reproduces the committed bound rather than a near miss of it. The
    committed rows also let `V_act` be recovered without recomputation, via
    `V_act = ceiling + EC(ask | b)` and the exact `EC(ask | b) = 2 + 2*b_h` of
    invariant 5, which is asserted here as a second, independent route to the same
    number.
    """
    by_id = {c["case_id"]: c for c in committed["per_arm"][arm]["per_case"]}
    if set(by_id) != {c["case_id"] for c in cases}:
        raise BaselineError(f"arm {arm!r} case ids differ from the committed artifact")

    worst_ceiling = worst_ec = worst_recovery = 0.0
    n_positive = 0
    for c in cases:
        ref = by_id[c["case_id"]]
        worst_ceiling = max(worst_ceiling, abs(-c["tier1_excess"] - ref["ceiling"]))
        # invariant 5, exact in rationals
        exact = 2 + 2 * Fraction(str(c["b_h"]))
        worst_ec = max(worst_ec, abs(c["ec_ask"] - float(exact)))
        recovered = ref["ceiling"] + c["ec_ask"]
        worst_recovery = max(worst_recovery, abs(c["v_act"] - recovered))
        if c["tier1_excess"] <= 0.0:
            n_positive += 1

    if worst_ceiling > ARTIFACT_TOL:
        raise BaselineError(
            f"arm {arm!r}: tier-1 excess disagrees with the committed ceiling by "
            f"{worst_ceiling:g}. The bound this gate quantifies has moved.")
    if worst_ec > TOL:
        raise BaselineError(f"arm {arm!r}: EC(ask|b) is not 2 + 2*b_h "
                            f"(worst {worst_ec:g})")
    if worst_recovery > ARTIFACT_TOL:
        raise BaselineError(f"arm {arm!r}: V_act does not match ceiling + EC(ask) "
                            f"(worst {worst_recovery:g})")
    if n_positive:
        raise BaselineError(
            f"arm {arm!r}: {n_positive} cases have a non-positive tier-1 excess, "
            "contradicting 400 committed negative ceilings. This is a bug, not a "
            "finding.")

    return {
        "source": "results/voi-ceiling-arms.json",
        "n_cases": len(cases),
        "max_ceiling_delta": worst_ceiling,
        "max_ec_ask_delta_from_2_plus_2bh": worst_ec,
        "max_v_act_recovery_delta": worst_recovery,
        "n_cases_with_non_positive_tier1_excess": n_positive,
        "note": ("The sign is the committed artifact's, reproduced here as a guard. "
                 "Its being negative on every case is not a result of this gate."),
    }


def invariant_census(cases: list[dict]) -> dict:
    """Invariants 2, 3, 4 and 6 across every case-question pair of one arm.

    Tested against actual VoI values for the first time in this project: invariants 2
    and 6 were stated at Gate 1 and proved analytically, but nothing had computed a
    `V_q` to check an implementation against them.
    """
    pairs = [(c, r) for c in cases for r in c["by_question"].values()]
    worst_2 = min(r["invariant_2_slack"] for _c, r in pairs)
    worst_3 = max(r["invariant_3_residual"] for _c, r in pairs)
    worst_6 = min(r["invariant_6_slack"] for _c, r in pairs)
    const = [(c, r) for c, r in pairs if r["argmin_constant_across_answers"]]
    worst_4 = max((r["invariant_4_residual"] for _c, r in const), default=0.0)

    if worst_2 < -TOL:
        raise BaselineError(f"invariant 2 violated: V_act - V_q = {worst_2:g} < 0. "
                            "A bug in the answer model or the Bayes update.")
    if worst_3 > TOL:
        raise BaselineError(f"invariant 3 violated: posteriors fail to average to "
                            f"the prior by {worst_3:g}")
    if worst_4 > TOL:
        raise BaselineError(f"invariant 4 violated: a constant argmin did not force "
                            f"V_q == V_act (worst {worst_4:g})")
    if worst_6 < -TOL:
        raise BaselineError(f"invariant 6 violated: VoI exceeds the committed "
                            f"ceiling by {-worst_6:g}")

    exact_ask_price = [
        (c, r) for c, r in const
        if abs(r["voi"] + r["ec_ask"]) <= TOL]
    # Invariant 6's slack is `V_q` identically: substituting the definition of VoI
    # into (V_act - EC_ask) - VoI cancels both other terms. Measured rather than
    # asserted, because a write-up that presented an algebraic identity as an
    # empirical check would be claiming a test it did not run.
    slack_is_v_q = max(abs(r["invariant_6_slack"] - r["v_q"]) for _c, r in pairs)
    attained = [(c, r) for c, r in pairs if r["invariant_6_slack"] <= TOL]
    return {
        "n_case_question_pairs": len(pairs),
        "invariant_2_min_slack": worst_2,
        "invariant_2_holds": worst_2 >= -TOL,
        "invariant_3_max_residual": worst_3,
        "invariant_3_holds": worst_3 <= TOL,
        "invariant_4_n_pairs_with_constant_argmin": len(const),
        "invariant_4_max_residual": worst_4,
        "invariant_4_holds": worst_4 <= TOL,
        "invariant_4_n_pairs_where_voi_is_exactly_minus_ec_ask": len(exact_ask_price),
        "invariant_6_min_slack": worst_6,
        "invariant_6_holds": worst_6 >= -TOL,
        "invariant_6_slack_equals_v_q_max_delta": slack_is_v_q,
        "what_invariant_6_actually_tests": (
            "Less than it looks. Substituting VoI = V_act - EC_ask - V_q into the "
            "slack (V_act - EC_ask) - VoI cancels both other terms and leaves V_q, "
            "measured above as agreeing to "
            f"{slack_is_v_q:.3g}. So on these definitions the invariant reduces to "
            "V_q >= 0, which holds because every entry of costs.COST is "
            "non-negative. It confirms the implementation is self-consistent; it is "
            "not independent evidence for the bound."),
        "where_the_independent_check_is": (
            "ceiling_agreement, which compares the recomputed EC(ask | b) - V_act(b) "
            "against the per-case ceilings committed in "
            "results/voi-ceiling-arms.json, and recovers V_act a second way via "
            "ceiling + EC(ask). That is what ties this gate's new code to Gate 4's "
            "analytic result."),
        "n_pairs_where_the_bound_is_attained": len(attained),
        "why_attainment_matters": (
            "V_q = 0 exactly on these pairs, so the ceiling is reached rather than "
            "merely bounding. A free perfect oracle driving the post-answer expected "
            "cost to zero still loses by the full -ceiling, which means the bound's "
            "negativity cannot be attributed to slack in the bound."),
        "what_invariant_4_means_here": (
            "Where the non-ask argmin is the same whatever the answer, the answer "
            "cannot change the action, so V_q == V_act exactly and the whole ask "
            "price is wasted: VoI = -EC(ask | b)."),
    }


# --------------------------------------------------------------------------- #
# 6. Invariant 8 — identity g, empty Q, reproducing v1
# --------------------------------------------------------------------------- #

def invariant_8(cases: list[dict], committed_rows: list[dict],
                committed_summary: dict) -> dict:
    """With `Q` empty there is nothing to ask, so the policy is v1's argmin.

    Asserted on all 100 per-case actions and on the committed test aggregate, not on
    the aggregate alone: two different action vectors can total the same cost.
    """
    by_id = {r["case_id"]: r for r in committed_rows}
    mismatches = []
    for c in cases:
        want = by_id[c["case_id"]]["decisions"]["cost_aware"]["action"]
        if c["v1_action"] != want:
            mismatches.append({"case_id": c["case_id"], "recomputed": c["v1_action"],
                               "committed": want})
    if mismatches:
        raise BaselineError(
            f"invariant 8 violated on {len(mismatches)} of {len(cases)} cases, e.g. "
            f"{mismatches[0]}. v2 does not contain v1 as a special case, so the "
            "comparison is not isolating the ask decision.")

    test = [c for c in cases if c["split"] == CLAIM_SPLIT]
    decisions = [{"action": c["v1_action"],
                  "realised_cost": ab.realised_cost(c["v1_action"], c["labels"]),
                  "needs_human": bool(c["labels"]["needs_human"])}
                 for c in test]
    got = ab.score(decisions)
    for key in ("total_cost", "mean_cost", "missed_escalations",
                "action_counts"):
        if got[key] != committed_summary[key]:
            raise BaselineError(
                f"invariant 8: recomputed test {key} is {got[key]!r}, committed is "
                f"{committed_summary[key]!r}")

    return {
        "what_it_checks": (
            "Identity g and Q empty reproduce v1's decisions on all 100 cases. "
            "Without it the comparison is not provably isolating the ask decision."),
        "n_cases_compared": len(cases),
        "n_mismatches": 0,
        "tie_break": "v1 legacy (ACTIONS order)",
        "why_legacy": (
            "Gate 4's safest-first rule differs from v1's on a11-repeated-097, where "
            "answer and hold tie at 0.000. Invariant 8 is on all 100 cases, so the "
            "rule that produced the committed decisions is the one used here."),
        "recomputed_test_aggregate": got,
        "committed_test_aggregate": {
            k: committed_summary[k] for k in
            ("total_cost", "mean_cost", "missed_escalations", "action_counts")},
        "agrees": True,
    }


# --------------------------------------------------------------------------- #
# 7. The threshold sweep — the magnitude this gate owes
# --------------------------------------------------------------------------- #

def _realised_expected(case: dict, question_id: str) -> float:
    """Expected realised cost of ask-then-act on one case, over the true state's row.

    The answer is drawn from `P(u | s_true)`, the same committed table that produced
    the prediction — which is what makes section 8 a self-consistency check. Exact in
    expectation, so no sampling is needed to report it; the seeded draw in
    `self_consistency` exists only to check this arithmetic.

    An answer the true state never gives contributes nothing, and an answer with zero
    predictive probability under the belief has no posterior to act on. Those are
    different sets, so a state-reachable answer with no belief branch would leave the
    follow-up action undefined and raises rather than being skipped.
    """
    labels = case["labels"]
    s_true = (labels["readiness"], bool(labels["needs_human"]))
    question = next(q for q in QUESTIONS if q.id == question_id)
    argmins = case["by_question"][question_id]["posterior_argmin_by_answer"]

    row = question.table[s_true]
    denom = sum(row)
    if denom <= 0:
        raise BaselineError(f"{question_id} has an all-zero row at {s_true}")

    total = float(costs.COST["ask"][s_true])
    for j, u in enumerate(question.answers):
        p = row[j] / denom
        if p <= 0.0:
            continue
        if u not in argmins:
            raise BaselineError(
                f"{case['case_id']}: the true state {s_true} can answer {u!r} but "
                f"the belief gives it zero probability, so there is no posterior to "
                "act on")
        total += p * costs.COST[argmins[u]][s_true]
    return total


def realised_monotonicity(test: list[dict], rows: list[dict],
                          fired_sets: list[set]) -> dict:
    """Whether the realised column falls as tau rises, and which case breaks it.

    The firing sets are nested by construction, since tau thresholds a scalar, so a
    case can only leave the firing set as tau rises. The expected tiers therefore fall
    monotonically: every firing case contributes a positive excess, so removing one
    can only reduce the total. The realised column carries no such guarantee. Dropping
    a case swaps its ask-then-act realised cost for v1's realised cost on that case,
    and v1's can be the dearer of the two whenever v1 answers a case it should have
    escalated.

    An inversion is therefore the expected/realised distinction showing up in the
    data, not a defect. The committed ceiling bounds expected cost under the belief
    and says nothing about any single realised draw. Reported because a reader who
    reads the realised column as monotone would take an inversion for an arithmetic
    error, and because the direction is worth stating: asking can win a case it was
    expected to lose.
    """
    for i in range(1, len(fired_sets)):
        if not fired_sets[i] <= fired_sets[i - 1]:
            raise BaselineError(
                f"firing sets are not nested between grid rows {i - 1} and {i}: "
                f"{sorted(fired_sets[i] - fired_sets[i - 1])} entered the set as tau "
                "rose, which a threshold on a scalar cannot do")

    by_id = {c["case_id"]: c for c in test}
    inversions = []
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        if cur["n_firing"] >= prev["n_firing"]:
            continue
        if cur["realised_total_cost"] <= prev["realised_total_cost"] + ARTIFACT_TOL:
            continue
        dropped = []
        for cid in sorted(fired_sets[i - 1] - fired_sets[i]):
            c = by_id[cid]
            ask = _realised_expected(c, c["oracle_question"])
            v1 = ab.realised_cost(c["v1_action"], c["labels"])
            dropped.append({
                "case_id": cid,
                "v1_action": c["v1_action"],
                "v1_realised_cost": v1,
                "ask_then_act_realised_cost": round(ask, 6),
                "realised_delta_from_dropping": round(v1 - ask, 6),
                "tier1_expected_excess": round(c["tier1_excess"], 6),
            })
        inversions.append({
            "between_quantiles": [prev["quantile"], cur["quantile"]],
            "n_firing": [prev["n_firing"], cur["n_firing"]],
            "realised_total_cost": [prev["realised_total_cost"],
                                    cur["realised_total_cost"]],
            "cases_that_stopped_firing": dropped,
        })

    tiers_are_monotone = all(
        rows[i]["tier1_total_excess"] <= rows[i - 1]["tier1_total_excess"]
        + ARTIFACT_TOL
        and rows[i]["tier2_total_excess"] <= rows[i - 1]["tier2_total_excess"]
        + ARTIFACT_TOL
        for i in range(1, len(rows)))
    if not tiers_are_monotone:
        raise BaselineError(
            "an expected tier rose as tau rose. Every firing case contributes a "
            "positive excess and the firing sets are nested, so this is impossible "
            "unless a per-case excess is non-positive, which ceiling_agreement "
            "already rules out.")

    return {
        "firing_sets_are_nested": True,
        "expected_tiers_are_monotone_in_tau": True,
        "why_the_tiers_must_be": (
            "Nested firing sets and a positive per-case excess. Checked, not assumed: "
            "a rise raises."),
        "realised_column_is_monotone_in_tau": not inversions,
        "n_inversions": len(inversions),
        "inversions": inversions,
        "what_an_inversion_means": (
            "A case left the firing set and v1's realised cost on it was dearer than "
            "ask-then-act's, so the total rose while the firing count fell. Expected "
            "cost is what the ceiling bounds; a single realised draw can go either "
            "way, and here it does."),
    }


def threshold_sweep(cases: list[dict], grid: dict, arm: str,
                    committed_fallback: dict) -> dict:
    """Firing counts and cost per threshold, on the claim split.

    Two ledgers, never summed. The expected ledger is tiers 1 and 2, in expected cost
    under the belief. The realised ledger scores against the labels, which is the
    currency v1's committed test total is in.

    The excess column is measured against this arm's own v1-policy total, not against
    published's 86. At tau = 1.0 nothing fires, so that row reproduces the arm's
    committed Gate 2 score and is checked against it here.
    """
    test = [c for c in cases if c["split"] == CLAIM_SPLIT]
    v1_total = sum(ab.realised_cost(c["v1_action"], c["labels"]) for c in test)
    v1_mean = v1_total / len(test)

    if (committed_fallback["total_cost"] != v1_total
            or abs(committed_fallback["mean_cost"] - v1_mean) > ARTIFACT_TOL):
        raise BaselineError(
            f"arm {arm!r}: v1's policy recomputed here scores {v1_total} total / "
            f"{v1_mean} mean on the {len(test)} {CLAIM_SPLIT} cases, but Gate 2 "
            f"committed {committed_fallback['total_cost']} / "
            f"{committed_fallback['mean_cost']} for this arm. Either the arm loader "
            "changed, the cost matrix changed, or the tie-break did.")

    rows = []
    fired_sets = []
    for g in grid["grid"]:
        tau = g["tau_bits_full"]
        firing = [c for c in test if c["h_bits"] > tau]
        fired = {c["case_id"] for c in firing}
        fired_sets.append(fired)
        t1 = sum(c["tier1_excess"] for c in firing)
        t2 = sum(c["tier2_excess"] for c in firing)
        realised = sum(
            _realised_expected(c, c["oracle_question"])
            if c["case_id"] in fired
            else ab.realised_cost(c["v1_action"], c["labels"])
            for c in test)
        rows.append({
            "quantile": g["quantile"],
            "tau_bits": g["tau_bits"],
            "tau_bits_full": tau,
            "n_firing": len(firing),
            "tier1_total_excess": round(t1, 6),
            "tier1_mean_excess_over_firing": round(t1 / len(firing), 6) if firing
            else None,
            "tier2_total_excess": round(t2, 6),
            "tier2_mean_excess_over_firing": round(t2 / len(firing), 6) if firing
            else None,
            "realised_total_cost": round(realised, 4),
            "realised_excess_over_v1": round(realised - v1_total, 4),
            "realised_mean_cost": round(realised / len(test), 4),
        })

    return {
        "population": f"the {len(test)} {CLAIM_SPLIT} cases",
        "firing_rule": "ask iff H_q(b) > tau, else the V_act argmin",
        "why_firing_sets_are_not_listed": (
            "Derivable from per_case h_bits and the tau column, so listing them "
            "would be a second copy that could drift from the first."),
        "v1_fallback_realised_total": v1_total,
        "v1_fallback_realised_mean": round(v1_mean, 4),
        "v1_fallback_committed": {
            "total_cost": committed_fallback["total_cost"],
            "mean_cost": committed_fallback["mean_cost"],
            "source": (f"results/rebaseline.json "
                       f"{'.'.join(COMMITTED_FALLBACK[arm])}"),
        },
        "reproduces_committed_fallback": True,
        "monotonicity": realised_monotonicity(test, rows, fired_sets),
        "why_the_reference_is_per_arm": (
            "realised_excess_over_v1 is measured against this arm's own v1-policy "
            "total, above, not against published's 86. v1's policy on rebuilt "
            "beliefs scores 70 on raw and 75 on calibrated; charging those arms an "
            "excess against 86 would compare them to a total they never had."),
        "thresholds": rows,
        "expected_ledger": (
            "tier1 and tier2 are expected cost under the belief. Tier 1 is "
            "answer-model-free because V_q >= 0 for any answer model; tier 2 uses "
            "the Gate 3 table."),
        "realised_ledger": (
            "realised_total_cost scores against the labels, exact in expectation "
            "over the answer, and is the only column comparable to v1's committed "
            "total. An expected excess added to a realised total would be neither."),
    }


def always_ask_anchor(cases: list[dict], grid: dict, committed: dict) -> dict:
    """The bottom of the grid against v1's committed `always_ask` row.

    At the 0th decile the baseline fires on every test case whose entropy is above
    the arm's minimum, which makes it comparable to a policy that always asks. The
    two are not equal and must not be: v1 prices `ask` as terminal at 142, this
    prices ask-then-act, so it has to be strictly dearer wherever the follow-up
    action costs anything.
    """
    test = [c for c in cases if c["split"] == CLAIM_SPLIT]
    tau0 = grid["grid"][0]["tau_bits_full"]
    firing = [c for c in test if c["h_bits"] > tau0]

    terminal = sum(ab.realised_cost("ask", c["labels"]) for c in test)
    then_act = sum(_realised_expected(c, c["oracle_question"]) for c in test)
    if then_act < terminal - TOL:
        raise BaselineError(
            f"ask-then-act ({then_act:g}) is cheaper than terminal ask "
            f"({terminal:g}); the follow-up action cannot reduce a realised cost")
    return {
        "v1_always_ask_committed": {
            "total_cost": committed["total_cost"],
            "mean_cost": committed["mean_cost"],
            "missed_escalations": committed["missed_escalations"],
            "pricing": "terminal — C(ask, s) and stop",
        },
        "gate5_all_test_cases_ask_then_act": {
            "total_cost": round(then_act, 4),
            "mean_cost": round(then_act / len(test), 4),
            "pricing": "C(ask, s) + C(a_u, s), expected over P(u | s_true)",
        },
        "terminal_ask_recomputed": round(terminal, 4),
        "recomputed_matches_committed": (
            abs(terminal - committed["total_cost"]) <= ARTIFACT_TOL),
        "n_firing_at_tau_0th_decile": len(firing),
        "n_test_cases": len(test),
        "why_they_differ": (
            "Terminal pricing charges the ask and stops; ask-then-act charges the "
            "ask and then the action the answer selects. Equality on every case "
            "would mean the follow-up is free everywhere, which is a bug."),
        "ask_then_act_is_dearer": then_act >= terminal - TOL,
    }


# --------------------------------------------------------------------------- #
# 8. The self-consistency check — not a validation
# --------------------------------------------------------------------------- #

def self_consistency(cases: list[dict]) -> dict:
    """A seeded draw against the exact expectation, on the claim split.

    What this is: a check that the simulator and the closed-form expectation agree,
    so the tier-3 arithmetic is right. What this is **not**: evidence that the answer
    model is right. The cases are single messages and contain no answer, so the
    answer is simulated from the same `P(u | s)` that produced the prediction. The
    check is therefore circular with respect to the answer model by construction.

    The words validation, validated, verified against reality and out-of-sample do
    not attach to this number. The Gate 3 `P(u | s)` sensitivity sweep is the
    load-bearing defence of the table, and the absence of external validation is a
    Limitations entry the paper gate owes.
    """
    test = [c for c in cases if c["split"] == CLAIM_SPLIT]
    rng = random.Random(SEED)
    exact = sum(_realised_expected(c, c["oracle_question"]) for c in test)

    drawn_total = 0.0
    for _ in range(N_DRAWS):
        for c in test:
            labels = c["labels"]
            s_true = (labels["readiness"], bool(labels["needs_human"]))
            q = next(q for q in QUESTIONS if q.id == c["oracle_question"])
            argmins = c["by_question"][q.id]["posterior_argmin_by_answer"]
            row = q.table[s_true]
            u = rng.choices(list(q.answers), weights=row, k=1)[0]
            drawn_total += (costs.COST["ask"][s_true]
                            + costs.COST[argmins[u]][s_true])
    mean_drawn = drawn_total / N_DRAWS

    return {
        "name": "self-consistency check of the implementation",
        "not_a_validation": (
            "The answer is simulated from the same P(u | s) that produced the "
            "prediction, so this is circular with respect to the answer model by "
            "construction. It checks arithmetic, not reality."),
        "seed": SEED,
        "n_draws": N_DRAWS,
        "seed_is_not_a_defence": (
            "The seed makes the number reproducible. It does nothing about the "
            "circularity above and is not offered as if it did."),
        "exact_expected_total": round(exact, 6),
        "monte_carlo_mean_total": round(mean_drawn, 6),
        "abs_delta": round(abs(mean_drawn - exact), 6),
        "relative_delta": round(abs(mean_drawn - exact) / exact, 8) if exact else None,
        "agrees_within_1pct": abs(mean_drawn - exact) <= 0.01 * exact,
        "external_validation": "none; the Limitations entry is the paper gate's",
    }


# --------------------------------------------------------------------------- #
# 9. Build
# --------------------------------------------------------------------------- #

def build_arm(arm: str, committed_ceilings: dict, run: dict,
              rebaseline: dict) -> dict:
    rows, source = vc.load_arm(arm)
    if len(rows) != 100:
        raise BaselineError(f"arm {arm!r} has {len(rows)} rows, expected 100")

    grid = ab.tau_grid(rows)
    cases = per_case(rows)
    summary = run["summaries"][CLAIM_SPLIT]["policies"]
    top, key = COMMITTED_FALLBACK[arm]
    fallback = rebaseline[top][key]

    out = {
        "source": source,
        "tau_grid": grid,
        "ceiling_agreement": ceiling_agreement(arm, cases, committed_ceilings),
        "invariants": invariant_census(cases),
        "threshold_sweep": threshold_sweep(cases, grid, arm, fallback),
        "always_ask_anchor": always_ask_anchor(cases, grid, summary["always_ask"]),
        "self_consistency": self_consistency(cases),
        "question_selection": {
            "oracle": "argmax_q VoI(q | b) over the three real questions",
            "n_test_cases_where_oracle_and_argmax_ig_agree": sum(
                1 for c in cases
                if c["split"] == CLAIM_SPLIT and c["oracle_and_ig_agree"]),
            "n_test_cases": sum(1 for c in cases if c["split"] == CLAIM_SPLIT),
            "argmax_ig_is_secondary": (
                "answer-model-dependent and ordering-fragile: 27 of 88 sweep "
                "variants flip the IG ordering of these three questions "
                "(results/answer-model.md), so it carries no headline."),
            "q_null_excluded_from_the_oracle": (
                "IG identically 0 at full ask price, so an oracle allowed to pick "
                "it could choose a dominated question. Kept in by_question as the "
                "zero-information reference."),
        },
        "per_case": [
            {k: v for k, v in c.items() if k != "by_question"} for c in cases],
    }
    if arm == "published":
        out["invariant_8"] = invariant_8(cases, run["rows"], summary["cost_aware"])
    else:
        out["invariant_8"] = {
            "checked_on": "the published arm only",
            "why": ("Invariant 8 is about reproducing v1's committed decisions, "
                    "which were made on v1's beliefs. Asserting it on a rebuilt "
                    "arm would be asserting that recalibration changed nothing."),
        }
    return out


def build_report() -> dict:
    committed_ceilings = json.loads(CEILING_ARMS_JSON.read_text(encoding="utf-8"))
    run = json.loads(RUN_JSON.read_text(encoding="utf-8"))
    rebaseline = json.loads(REBASELINE_JSON.read_text(encoding="utf-8"))
    rows, _ = vc.load_arm("published")

    return {
        "what_this_is": (
            "The cost of the entropy-threshold ask baseline, on four belief arms "
            "over the pre-registered decile grid for tau, and the first per-case "
            "VoI computation in this project."),
        "pre_registration": "decisions/v2-gate5-preregistration.md",
        "sign_is_committed": {
            "claim": (
                "Every excess reported here is positive because all 400 committed "
                "per-case ceilings are negative and the unconstrained-menu maximum "
                "is -2/13 in closed form. This gate reproduces the sign as a "
                "regression guard and quantifies the magnitude."),
            "sources": ["results/voi-ceiling.json", "results/voi-ceiling-arms.json"],
            "what_would_be_a_bug": (
                "A non-positive excess anywhere. It contradicts a committed "
                "invariant, so ceiling_agreement raises rather than reporting it."),
            "what_is_new_here": (
                "The firing index set per threshold, the cost magnitude, the first "
                "computed V_q and VoI, and the finding that the committed ceiling is "
                "attained exactly on some pairs rather than merely bounding them."),
        },
        "beliefs": {
            "arms": list(ARMS),
            "n_cases_per_arm": 100,
            "claim_split": CLAIM_SPLIT,
            "why_four_arms": (
                "Matches results/voi-ceiling-arms.json, which this gate reads for "
                "the per-case ceilings, so no column is dropped."),
            "rebaselined_carries_no_claim": (
                "Gate 4's abstention run scored three arms because 'rebaselined "
                "would add a column about cache drift, which abstention has nothing "
                "to do with' (results/abstention.json beliefs."
                "why_three_arms_not_four). That reason applies to entropy "
                "thresholding too. The column is kept for consistency and is a "
                "cache-drift column: no sentence in this artifact or the paper "
                "rests on it."),
            "dev_is_in_sample": (
                "The isotonic map was fitted on dev, so calibrated b_h on the dev "
                "half is in-sample. Claims are test-only."),
        },
        "adapter": adapter_agreement(rows),
        "definitions": {
            "v_act": "min over F \\ {ask} of EC(a | b)",
            "v_q": "sum_u P_b(u) * V_act(b^u)",
            "voi": "V_act(b) - [EC(ask | b) + V_q(b)]",
            "why_v_act_inside_v_q": (
                "One question, so the agent cannot ask again after the answer. "
                "Relaxing that is Gate 6's boundary."),
            "the_wrong_form": (
                "V(b) - V_q(b) - EC(ask | b) is a tautology because "
                "V(b) <= EC(ask | b) identically once ask is on the menu. Not "
                "computed here."),
            "constraints_survive_the_answer": (
                "A constraint is a case-level fact about what the agent may do, so "
                "the same non-ask menu applies at the prior and at every posterior."),
            "units": (
                "Bits select and trip thresholds; cost points score. No bit value "
                "is compared to a cost value anywhere in this script."),
        },
        "s4_inventory": {
            "tau": ("deciles of the observed H(b) distribution on the arm being "
                    "scored, imported from experiments/abstention.py unchanged"),
            "h_decimals": (H_DECIMALS, "derived at Gate 4 against the measured "
                                       "float-noise bound; carried, not re-chosen"),
            "exact_rationals": ["-2/13", "3/13", "1/5", "6/23"],
            "tolerances": {"float": TOL, "against_6dp_artifacts": ARTIFACT_TOL},
            "n_new_tunables_introduced_at_this_gate": 0,
        },
        "arms": {arm: build_arm(arm, committed_ceilings, run, rebaseline)
                 for arm in ARMS},
    }


# --------------------------------------------------------------------------- #
# 10. Rendering
# --------------------------------------------------------------------------- #

def render(report: dict) -> str:
    out: list[str] = []
    w = out.append

    w("# The cost of thresholding on entropy, and the first VoI numbers")
    w("")
    w(report["what_this_is"])
    w("")
    w(f"Pre-registered in `{report['pre_registration']}`.")
    w("")
    w("## The sign is committed, the magnitude is the result")
    w("")
    w(report["sign_is_committed"]["claim"])
    w("")
    w(f"New here: {report['sign_is_committed']['what_is_new_here']}")
    w("")

    w("## The cost-side adapter")
    w("")
    ad = report["adapter"]
    w(ad["why_it_is_needed"])
    w("")
    w(f"`ec_joint` against `costs.expected_cost` on {ad['n_comparisons']} "
      f"(prior, action) pairs: max delta {ad['max_abs_delta']:.3g}.")
    w("")

    w("## Invariants, against computed VoI rather than the bound")
    w("")
    w("| arm | pairs | inv 2 min slack | inv 3 max resid | inv 4 constant argmin "
      "| inv 6 min slack | bound attained |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    for arm in report["beliefs"]["arms"]:
        i = report["arms"][arm]["invariants"]
        w(f"| `{arm}` | {i['n_case_question_pairs']} | "
          f"{i['invariant_2_min_slack']:.3g} | {i['invariant_3_max_residual']:.3g} | "
          f"{i['invariant_4_n_pairs_with_constant_argmin']} | "
          f"{i['invariant_6_min_slack']:.3g} | "
          f"{i['n_pairs_where_the_bound_is_attained']} |")
    w("")
    pub = report["arms"]["published"]["invariants"]
    w(f"**What invariant 6 actually tests.** {pub['what_invariant_6_actually_tests']}")
    w("")
    w(f"**Where the independent check is.** {pub['where_the_independent_check_is']}")
    w("")
    w("| arm | recomputed vs committed ceiling | EC(ask) vs 2+2b_h | V_act recovery |")
    w("| --- | --- | --- | --- |")
    for arm in report["beliefs"]["arms"]:
        c = report["arms"][arm]["ceiling_agreement"]
        w(f"| `{arm}` | {c['max_ceiling_delta']:.3g} | "
          f"{c['max_ec_ask_delta_from_2_plus_2bh']:.3g} | "
          f"{c['max_v_act_recovery_delta']:.3g} |")
    w("")
    w(f"**The bound is attained.** {pub['why_attainment_matters']}")
    w("")
    w(pub["what_invariant_4_means_here"])
    w("")

    w("## Invariant 8")
    w("")
    i8 = report["arms"]["published"]["invariant_8"]
    w(f"{i8['what_it_checks']} Compared on {i8['n_cases_compared']} cases, "
      f"{i8['n_mismatches']} mismatches, tie-break {i8['tie_break']}.")
    w("")
    w(f"Recomputed test aggregate `{i8['recomputed_test_aggregate']['total_cost']}` "
      f"total, mean `{i8['recomputed_test_aggregate']['mean_cost']}` — equal to the "
      "committed row.")
    w("")

    w("## Firing counts and cost per threshold")
    w("")
    w(report["arms"]["published"]["threshold_sweep"]["expected_ledger"])
    w("")
    w(report["arms"]["published"]["threshold_sweep"]["realised_ledger"])
    w("")
    for arm in report["beliefs"]["arms"]:
        sw = report["arms"][arm]["threshold_sweep"]
        note = (" — cache-drift column, carries no claim"
                if arm == "rebaselined" else "")
        w(f"### `{arm}`{note}")
        w("")
        w(f"v1's policy on this arm's beliefs, same 50 cases: "
          f"{sw['v1_fallback_realised_total']} total, mean "
          f"{sw['v1_fallback_realised_mean']} — reproduces "
          f"{sw['v1_fallback_committed']['source']}. The excess column is measured "
          f"against this arm's own total, which is why raw and calibrated are not "
          f"charged against published's 86.")
        w("")
        w("| quantile | tau (bits) | firing | tier 1 total | tier 2 total "
          "| realised total | realised excess |")
        w("| --- | --- | --- | --- | --- | --- | --- |")
        for r in sw["thresholds"]:
            w(f"| {r['quantile']:.1f} | {r['tau_bits']:.4f} | {r['n_firing']} | "
              f"{r['tier1_total_excess']:.4f} | {r['tier2_total_excess']:.4f} | "
              f"{r['realised_total_cost']:.2f} | "
              f"{ab._sign(r['realised_excess_over_v1'])} |")
        w("")
        mono = sw["monotonicity"]
        for inv in mono["inversions"]:
            lo, hi = inv["between_quantiles"]
            nf_lo, nf_hi = inv["n_firing"]
            c_lo, c_hi = inv["realised_total_cost"]
            w(f"Between quantiles {lo:.1f} and {hi:.1f} the firing count falls "
              f"{nf_lo} to {nf_hi} and the realised total rises {c_lo:.2f} to "
              f"{c_hi:.2f}.")
            for d in inv["cases_that_stopped_firing"]:
                w(f"- `{d['case_id']}` stopped firing: v1 plays "
                  f"`{d['v1_action']}` for realised {d['v1_realised_cost']}, "
                  f"ask-then-act realised {d['ask_then_act_realised_cost']:.2f}, so "
                  f"dropping it costs {d['realised_delta_from_dropping']:+.2f}. Its "
                  f"expected tier-1 excess is still "
                  f"{d['tier1_expected_excess']:+.4f}.")
            w("")
            w(mono["what_an_inversion_means"])
            w("")

    w("## The always_ask anchor")
    w("")
    a = report["arms"]["published"]["always_ask_anchor"]
    w(a["why_they_differ"])
    w("")
    w(f"v1 terminal: {a['v1_always_ask_committed']['total_cost']} total, mean "
      f"{a['v1_always_ask_committed']['mean_cost']}. Ask-then-act on the same 50 "
      f"cases: {a['gate5_all_test_cases_ask_then_act']['total_cost']} total, mean "
      f"{a['gate5_all_test_cases_ask_then_act']['mean_cost']}.")
    w("")

    w("## Self-consistency")
    w("")
    sc = report["arms"]["published"]["self_consistency"]
    w(f"**{sc['name']}.** {sc['not_a_validation']}")
    w("")
    w(f"Exact expectation {sc['exact_expected_total']}, Monte Carlo mean over "
      f"{sc['n_draws']} draws {sc['monte_carlo_mean_total']}, delta "
      f"{sc['abs_delta']}. Seed {sc['seed']}. {sc['seed_is_not_a_defence']}")
    w("")

    w("## Question selection")
    w("")
    qs = report["arms"]["published"]["question_selection"]
    w(f"Oracle: {qs['oracle']}. It agrees with argmax-IG on "
      f"{qs['n_test_cases_where_oracle_and_argmax_ig_agree']} of "
      f"{qs['n_test_cases']} test cases.")
    w("")
    w(qs["argmax_ig_is_secondary"])
    w("")
    w(qs["q_null_excluded_from_the_oracle"])
    w("")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--md", type=Path, default=None)
    args = parser.parse_args()

    report = build_report()
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    if args.md:
        args.md.write_text(render(report), encoding="utf-8")
        print(f"wrote {args.md}")
    if not args.json and not args.md:
        print(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
