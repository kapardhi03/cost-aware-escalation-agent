"""
voi_boundary.py — where a policy that may ask actually starts asking.

Usage
    python experiments/voi_boundary.py

Reads results/run.json for the committed beliefs and constraints. Writes
results/voi-boundary.json and .md. Runs no model; every quantity is exact rational
arithmetic on numbers that are already committed.

WHAT THE TWO POLICIES ARE
P2 is the shipped rule: argmin of expected cost over the feasible actions, `ask`
among them, no lookahead. P3 keeps P2's menu and adds one step of lookahead — it
prices `ask` as the question's charge PLUS what it expects to pay after the answer
arrives, instead of as the charge alone. That is the only difference. On every case
where P3 does not ask, it plays P2's action by construction, because its non-ask
comparison IS P2's comparison.

WHY THERE ARE TWO VERSIONS OF P3
  oracle  the post-answer act cost is taken to be zero, i.e. the answer is assumed
          to resolve the state. This is not a policy anyone would ship; it is the
          quantity Theorem 1 bounds, and its switch point is the largest lambda at
          which ANY question could be worth its price.
  real    the post-answer act cost is the actual expected cost of acting on the
          actual posterior, question by question, from the committed answer model in
          src/questions.py. Its switch point is the largest lambda at which a
          question that exists is worth its price.
The gap between them is the distance between the theorem's bound and the answers
available, and reporting one without the other would hide it.

WHY EXPECTED COST IS COMPUTED ON THE SIX-VECTOR JOINT
costs.expected_cost takes a Belief, which is a readiness marginal plus a scalar, and
so can only score beliefs that factorise. Posteriors generally do not: an answer
whose likelihood depends on both halves of the state couples them. src.questions
already refuses to pretend otherwise — `narrow` raises NonFactorisingError rather
than projecting a coupled posterior onto its marginals. So `ec_joint` scores actions
against the full six-state distribution, and `joint_agrees_with_expected_cost`
checks it against costs.expected_cost on the 100 priors, which DO factorise.

THE TIE-BREAK IS HELD FIXED
The order comes from the unscaled matrix and does not move with lambda, even though
`ask`'s worst case does. Repricing the ask row is the counterfactual; letting the
convention drift with it would put two things in motion and leave the switch point
attributable to neither. A case counts as asking on a STRICT inequality, so at
lambda exactly equal to a switch point the case does not ask, and no reported
boundary rests on a tie.

WHAT IS PREDICTED, BEFORE IT RAN
Stated in PREREGISTRATION below and checked by `compare`. Unlike the plug-in arm's
pre-registration, which restated a specification, and unlike the results table's,
which restated arithmetic, this one is a prediction: the switch points were not
known when it was written. The honesty rule it is written under is that a measured
switch is reported where it lands. An offset from the analytic boundary is a result
with a cause to be named, not an error to be rounded away.
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from src.costs import (ACTIONS, COST, choose_action, expected_cost,  # noqa: E402
                       feasible_actions, tie_break_order)
from src.belief import Belief                                        # noqa: E402
from src.questions import NEEDS_HUMAN, QUESTIONS, READINESS          # noqa: E402

RUN_PATH = ROOT / "results" / "run.json"
CEILING_PATH = ROOT / "results" / "voi-ceiling.json"
OUT_JSON = ROOT / "results" / "voi-boundary.json"
OUT_MD = ROOT / "results" / "voi-boundary.md"

STATES = tuple((r, h) for h in NEEDS_HUMAN for r in READINESS)
ACT_ACTIONS = tuple(a for a in ACTIONS if a != "ask")

#: The analytic boundary, already committed in results/voi-ceiling.json. Read from
#: that file at runtime rather than typed here, so this script cannot drift from it.
ANALYTIC_LAMBDA_KEY = "break_even_lambda_exact"

# --------------------------------------------------------------------------- #
# Pre-registration
# --------------------------------------------------------------------------- #

#: Written down before the script ran, and a genuine prediction: none of these
#: values had been computed. P1-P3 follow from the committed matrix and the decile
#: structure of the belief set; P4-P6 are about the answer model and were guessed
#: from the shape of the act comparison, not derived.
PREREGISTRATION = {
    # P1. THE REAL-MENU RESULT. At lambda = 1 no case asks, under either version of
    # P3, for any of the four questions, so P3 and P2 agree on all 100 decisions and
    # on total realised cost. This is Theorem 1's consequence measured rather than
    # argued, and it is the finding of this arm, not a null result.
    "asks_at_lambda_1_oracle": 0,
    "asks_at_lambda_1_real": 0,
    "p3_equals_p2_at_lambda_1": True,

    # P2. The oracle switch lands at 5/6, strictly below the analytic 15/16. The
    # ratio V_act/EC_ask along the answer/notify boundary is 5*b_h/(1 + b_h) below
    # the crossing at b_h = 3/13 and 3(1 - b_h)/(2 + 2*b_h) above it, so it peaks AT
    # 3/13, which is not a decile. Committed b_h values are deciles: 0.2 gives 5/6
    # and 0.3 gives 21/26. Conditional on some b_h = 0.2 case whose `hold` and
    # `pause` both exceed 2.0, the max is 5/6.
    "lambda_star_oracle": "5/6",

    # P3. So the offset is 15/16 - 5/6 = 5/48, and its cause is the quantization of
    # b_h to deciles around 3/13 -- not the tie-break, which is held fixed, and not
    # the algebra, which the crosscheck re-derives.
    "offset_from_analytic": "5/48",
    "offset_cause": "belief quantization",

    # P4. The real switch is strictly below the oracle switch, and far below: the
    # oracle credits an answer with the whole act cost, while a real answer shifts
    # the act decision on few cases. Predicted under 0.25.
    "lambda_star_real_below_oracle": True,
    "lambda_star_real_under_quarter": True,

    # P5. The question that achieves the real switch is q_authority, because the act
    # comparison at the boundary turns on b_h and that is the question aimed at it.
    "argmax_question": "q_authority",

    # P6. q_null is uninformative by construction, so its posterior is its prior,
    # its lookahead value equals V_act, and its switch point is exactly zero.
    "q_null_lambda_is_zero": True,
}


# --------------------------------------------------------------------------- #
# Exact arithmetic on beliefs, posteriors and actions
# --------------------------------------------------------------------------- #

RANK = {a: i for i, a in enumerate(tie_break_order(COST))}


def prior_joint(belief: dict) -> dict:
    """The committed belief as an exact six-vector over joint states.

    run.json stores the belief rounded to six decimal places, so Fraction(str(v))
    recovers the decimal that was written and not a binary approximation of it. The
    readiness sum is asserted rather than assumed: a belief that does not sum to one
    would make every ratio below meaningless in a way no later check would catch.
    """
    r = {k: Fraction(str(belief["readiness"][k])) for k in READINESS}
    h = Fraction(str(belief["needs_human"]))
    if sum(r.values()) != 1:
        raise ValueError(f"readiness sums to {sum(r.values())}, not 1: {r}")
    if not 0 <= h <= 1:
        raise ValueError(f"needs_human out of range: {h}")
    return {(k, needs): r[k] * (h if needs else 1 - h)
            for k in READINESS for needs in NEEDS_HUMAN}


def ec_joint(action: str, joint: dict, ask_scale: Fraction = Fraction(1)) -> Fraction:
    """Expected cost of one action against a joint distribution, exactly.

    `ask_scale` multiplies the ask row and only the ask row. That is the whole
    counterfactual: the practitioner's other four rows are held at the values they
    were set to, and the question's price is the single thing that moves.
    """
    scale = ask_scale if action == "ask" else Fraction(1)
    return sum(joint[s] * Fraction(str(COST[action][s])) * scale for s in STATES)


def v_act(joint: dict, menu: tuple) -> tuple:
    """Cheapest feasible action that is not a question, and its expected cost.

    This is P2's comparison with `ask` struck out. On any case where P3 declines to
    ask, this is P3's decision too, which is why P3 needs no separate act rule.
    """
    scored = {a: ec_joint(a, joint) for a in menu}
    best = min(menu, key=lambda a: (scored[a], RANK[a]))
    return scored[best], best


def posteriors(question, joint: dict) -> list:
    """Answer-by-answer predictive weight and posterior joint, exactly.

    P(u) = sum_s b(s) L(u|s); b^u(s) = b(s) L(u|s) / P(u). Assumption A2 of the
    answer model is that every answer has positive probability under every state, so
    no branch is dropped here and no division is guarded -- if A2 ever fails the
    ZeroDivisionError is the correct outcome, not a filtered answer.
    """
    out = []
    for u in question.answers:
        weights = {s: joint[s] * question.likelihood(s, u) for s in STATES}
        p_u = sum(weights.values())
        out.append((u, p_u, {s: w / p_u for s, w in weights.items()}))
    return out


def factorises_exactly(joint: dict) -> bool:
    """Whether a joint distribution is a product of its own marginals, exactly.

    src.questions.factorises does this in floating point with a tolerance, which is
    right for an artifact that reports near-independence. Here the question is
    whether costs.expected_cost COULD have scored this distribution at all, and that
    is a yes-or-no fact about exact rationals.
    """
    h = sum(joint[(r, True)] for r in READINESS)
    r_marg = {r: joint[(r, False)] + joint[(r, True)] for r in READINESS}
    return all(joint[(r, needs)] == r_marg[r] * (h if needs else 1 - h)
               for r in READINESS for needs in NEEDS_HUMAN)


# --------------------------------------------------------------------------- #
# The switch, located exactly
# --------------------------------------------------------------------------- #

def per_case(row: dict) -> dict:
    """Every break-even lambda this case supplies, in exact rationals.

    P3 asks iff lambda * EC_ask + V_after < V_act, so the case's break-even lambda is
    (V_act - V_after) / EC_ask -- one number, solved for, not searched for. The
    oracle takes V_after = 0, which is Theorem 1's bound; the real arm takes
    V_after = sum_u P(u) * V_act(b^u), the lookahead value of that question.

    V_act - V_q is non-negative for every question because V_act is a min of linear
    functions, hence concave, and the prior is the predictive mixture of the
    posteriors. So every real break-even is a point in [0, oracle], and `checks`
    below asserts that rather than trusting it.
    """
    joint = prior_joint(row["belief"])
    menu = tuple(a for a in feasible_actions(row["constraints"]) if a != "ask")
    ec_ask = ec_joint("ask", joint)
    act, act_action = v_act(joint, menu)

    questions = {}
    for q in QUESTIONS:
        post = posteriors(q, joint)
        v_q = sum(p_u * v_act(b_u, menu)[0] for _, p_u, b_u in post)
        questions[q.id] = {
            "lookahead_value": str(v_q),
            "gain": str(act - v_q),
            "lambda_star": str((act - v_q) / ec_ask),
            "lambda_star_float": float((act - v_q) / ec_ask),
            "posterior_actions": {u: v_act(b_u, menu)[1] for u, _, b_u in post},
            "answer_changes_the_action": sorted(
                {v_act(b_u, menu)[1] for _, _, b_u in post}) != [act_action],
            "all_posteriors_factorise": all(
                factorises_exactly(b_u) for _, _, b_u in post),
        }

    best_q = max(questions, key=lambda k: Fraction(questions[k]["lambda_star"]))
    return {
        "case_id": row["case_id"],
        "needs_human_belief": str(Fraction(str(row["belief"]["needs_human"]))),
        "constrained": bool(row["constraints"]),
        "menu": list(menu),
        "ec_ask": str(ec_ask),
        "v_act": str(act),
        "act_action": act_action,
        "p2_action": row["decisions"]["cost_aware"]["action"],
        "p2_action_corrected": choose_action(
            Belief.from_dict(row["belief"]), row["constraints"],
            matrix=COST).action,
        "lambda_oracle": str(act / ec_ask),
        "lambda_oracle_float": float(act / ec_ask),
        "questions": questions,
        "lambda_real": questions[best_q]["lambda_star"],
        "lambda_real_float": questions[best_q]["lambda_star_float"],
        "best_question": best_q,
    }

# --------------------------------------------------------------------------- #
# The grid, as a cross-check on the closed form
# --------------------------------------------------------------------------- #

def decide_at(row: dict, lam: Fraction, oracle: bool) -> dict:
    """P3's decision on one case at one lambda, by direct comparison.

    This re-runs the comparison instead of consulting the break-even, so that the
    grid can disagree with the closed form. That is the point of having it: a switch
    point nobody could contradict is a number, not a measurement. The pattern is
    voi_ceiling.py's -- solve it, then check it with something too dumb to be wrong.
    """
    joint = prior_joint(row["belief"])
    menu = tuple(a for a in feasible_actions(row["constraints"]) if a != "ask")
    act, act_action = v_act(joint, menu)
    charge = ec_joint("ask", joint, ask_scale=lam)

    best_q, best_total = None, None
    for q in QUESTIONS:
        after = (Fraction(0) if oracle else
                 sum(p_u * v_act(b_u, menu)[0]
                     for _, p_u, b_u in posteriors(q, joint)))
        total = charge + after
        if best_total is None or total < best_total:
            best_q, best_total = q.id, total

    asks = best_total < act
    return {"asks": asks, "action": "ask" if asks else act_action,
            "question": best_q if asks else None}


def realised(row: dict, decision: dict, lam: Fraction) -> Fraction:
    """Realised cost of one decision, under the pricing convention already in use.

    Terminal and holding actions are priced against the true state. `ask` is priced
    as the scaled charge plus the expectation, over the true state's row of the
    answer model, of what the action taken on the resulting posterior costs in that
    same true state. This is entropy_baseline._realised_expected's convention, reused
    rather than reinvented so that an asking policy's cost here is comparable to the
    asking policy's cost there; it is exact, so nothing is sampled.
    """
    s_true = (row["labels"]["readiness"], bool(row["labels"]["needs_human"]))
    if not decision["asks"]:
        return Fraction(str(COST[decision["action"]][s_true]))

    joint = prior_joint(row["belief"])
    menu = tuple(a for a in feasible_actions(row["constraints"]) if a != "ask")
    q = next(x for x in QUESTIONS if x.id == decision["question"])
    after = sum(q.likelihood(s_true, u)
                * Fraction(str(COST[v_act(b_u, menu)[1]][s_true]))
                for u, _, b_u in posteriors(q, joint))
    return lam * Fraction(str(COST["ask"][s_true])) + after


def sweep(rows: list, cases: list, grid: list) -> list:
    """Ask counts and realised cost across lambda, both versions, both ways.

    `predicted_*` counts come from the exact break-evens; `measured_*` from
    decide_at. They are compared field by field in `checks`.
    """
    out = []
    for lam in grid:
        oracle = [decide_at(r, lam, True) for r in rows]
        real = [decide_at(r, lam, False) for r in rows]
        out.append({
            "lambda": str(lam),
            "lambda_float": float(lam),
            "measured_asks_oracle": sum(d["asks"] for d in oracle),
            "measured_asks_real": sum(d["asks"] for d in real),
            "predicted_asks_oracle":
                sum(Fraction(c["lambda_oracle"]) > lam for c in cases),
            "predicted_asks_real":
                sum(Fraction(c["lambda_real"]) > lam for c in cases),
            "real_agrees_with_p2":
                sum(d["action"] == r["decisions"]["cost_aware"]["action"]
                    for d, r in zip(real, rows)),
            "real_agrees_with_p2_corrected":
                sum(d["action"] == c["p2_action_corrected"]
                    for d, c in zip(real, cases)),
            "mean_realised_real": float(
                sum(realised(r, d, lam) for r, d in zip(rows, real)) / len(rows)),
            "questions_used": sorted({d["question"] for d in real if d["asks"]}),
        })
    return out

# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #

def joint_agrees_with_expected_cost(rows: list) -> dict:
    """Does ec_joint score the priors the way costs.expected_cost does?

    The priors factorise, so both functions apply and must agree; the posteriors are
    where only one of them does. Without this check `ec_joint` would be an
    unvalidated second implementation of the paper's cost model, and every lambda
    below would rest on it.
    """
    worst, n = 0.0, 0
    for r in rows:
        joint, belief = prior_joint(r["belief"]), Belief.from_dict(r["belief"])
        for a in ACTIONS:
            worst = max(worst, abs(float(ec_joint(a, joint))
                                   - expected_cost(a, belief, COST)))
            n += 1
    return {"comparisons": n, "max_abs_difference": worst, "agrees": worst < 1e-9}


def checks(cases: list, grid_rows: list, analytic: Fraction,
           lam_oracle: Fraction, lam_real: Fraction) -> dict:
    """Everything that must hold if the reported switch points mean anything."""
    return {
        "grid_matches_closed_form_oracle":
            all(g["measured_asks_oracle"] == g["predicted_asks_oracle"]
                for g in grid_rows),
        "grid_matches_closed_form_real":
            all(g["measured_asks_real"] == g["predicted_asks_real"]
                for g in grid_rows),
        "every_real_break_even_within_oracle":
            all(0 <= Fraction(q["lambda_star"]) <= Fraction(c["lambda_oracle"])
                for c in cases for q in c["questions"].values()),
        "p2_never_asks": all(c["p2_action"] != "ask" for c in cases),
        "p2_never_asks_corrected":
            all(c["p2_action_corrected"] != "ask" for c in cases),
        "p3_act_choice_is_p2s":
            all(c["act_action"] == c["p2_action_corrected"] for c in cases),
        "oracle_below_analytic": lam_oracle < analytic,
        "real_below_oracle": lam_real < lam_oracle,
        "q_null_never_pays":
            all(Fraction(c["questions"]["q_null"]["lambda_star"]) == 0
                for c in cases),
        "some_posterior_does_not_factorise":
            any(not q["all_posteriors_factorise"]
                for c in cases for qid, q in c["questions"].items()
                if qid != "q_null"),
    }


def compare(measured: dict) -> dict:
    """Measured against what was written down, field by field."""
    got = {
        "asks_at_lambda_1_oracle": measured["at_lambda_1"]["measured_asks_oracle"],
        "asks_at_lambda_1_real": measured["at_lambda_1"]["measured_asks_real"],
        "p3_equals_p2_at_lambda_1":
            measured["at_lambda_1"]["real_agrees_with_p2_corrected"]
            == measured["n_cases"],
        "lambda_star_oracle": measured["lambda_star_oracle"],
        "offset_from_analytic": measured["offset_from_analytic"],
        "offset_cause": measured["offset_cause"],
        "lambda_star_real_below_oracle": measured["checks"]["real_below_oracle"],
        "lambda_star_real_under_quarter":
            Fraction(measured["lambda_star_real"]) < Fraction(1, 4),
        "argmax_question": measured["argmax_question"],
        "q_null_lambda_is_zero": measured["checks"]["q_null_never_pays"],
    }
    return {
        "status": "a prediction: none of these values were known when it was "
                  "written. Any field that reads False is the result, not a bug.",
        "fields": {k: {"predicted": PREREGISTRATION[k], "measured": got[k],
                       "match": PREREGISTRATION[k] == got[k]} for k in got},
        "all_match": all(PREREGISTRATION[k] == got[k] for k in got),
    }

# --------------------------------------------------------------------------- #
# Why the empirical switch is not the analytic one
# --------------------------------------------------------------------------- #

def diagnose_offset(rows: list, analytic: Fraction, lam_oracle: Fraction) -> dict:
    """Name the cause of the offset, or refuse to name one.

    The claim on offer is that the gap is the belief set and not the algebra. It is
    not asserted: the witness belief from results/voi-ceiling.json is pushed through
    THIS script's own ec_joint and v_act, and if the offset is quantization then that
    belief must score exactly the analytic lambda while no committed belief can reach
    it. Both halves have to hold. If either fails the cause is recorded as
    unexplained, because a gap with the wrong explanation is worse than a gap.
    """
    witness = {(r, needs): (Fraction(3, 13) if needs else Fraction(10, 13))
               if r == "hot" else Fraction(0)
               for r in READINESS for needs in NEEDS_HUMAN}
    w_act, _ = v_act(witness, ACT_ACTIONS)
    w_lambda = w_act / ec_joint("ask", witness)

    grid_step = Fraction(1, 10)
    b_h = sorted({Fraction(str(r["belief"]["needs_human"])) for r in rows})
    on_grid = all(v % grid_step == 0 for v in b_h)
    neighbours = (max((v for v in b_h if v < Fraction(3, 13)), default=None),
                  min((v for v in b_h if v > Fraction(3, 13)), default=None))

    explained = (w_lambda == analytic and on_grid
                 and Fraction(3, 13) % grid_step != 0)
    return {
        "witness_lambda": str(w_lambda),
        "witness_reproduces_analytic": w_lambda == analytic,
        "analytic_optimum_b_h": str(Fraction(3, 13)),
        "committed_b_h_values": [str(v) for v in b_h],
        "committed_b_h_all_on_deciles": on_grid,
        "optimum_is_on_the_decile_grid": Fraction(3, 13) % grid_step == 0,
        "nearest_committed_b_h_below_and_above":
            [str(v) if v is not None else None for v in neighbours],
        "no_committed_belief_at_the_optimum": Fraction(3, 13) not in b_h,
        "offset": str(analytic - lam_oracle),
        "offset_float": float(analytic - lam_oracle),
        "cause": "belief quantization" if explained else "unexplained",
    }


def lambda_curve(rows: list) -> list:
    """The oracle break-even at each distinct committed b_h, for the offset story.

    The peak of this curve is the empirical switch, and printing the curve is what
    turns "the switch is below the boundary" into "the switch is at the decile
    nearest the boundary's argmax, on the side the curve rises from".
    """
    by_b_h: dict = {}
    for r in rows:
        b_h = Fraction(str(r["belief"]["needs_human"]))
        joint = prior_joint(r["belief"])
        menu = tuple(a for a in feasible_actions(r["constraints"]) if a != "ask")
        lam = v_act(joint, menu)[0] / ec_joint("ask", joint)
        prev = by_b_h.get(b_h)
        if prev is None or lam > Fraction(prev["max_lambda"]):
            by_b_h[b_h] = {"b_h": str(b_h), "max_lambda": str(lam),
                           "max_lambda_float": float(lam),
                           "attained_by": r["case_id"],
                           "n_cases": 0}
        by_b_h[b_h]["n_cases"] += 1
    return [by_b_h[k] for k in sorted(by_b_h)]
def tie_break_gap(cases: list) -> dict:
    """Where P3's act choice differs from the decision committed in run.json.

    It differs on exactly the cases the tie-break correction already moves, and the
    comparison in `checks` is made against the corrected rule for that reason. This
    is not a redefinition of the target to let a prediction pass: the disagreement is
    reported here by case, run.json is the file generated under the legacy order, and
    P3 is a new arm which has no reason to inherit a convention the paper already
    describes as superseded.
    """
    differ = [{"case_id": c["case_id"], "committed": c["p2_action"],
               "corrected": c["p2_action_corrected"], "p3_act": c["act_action"]}
              for c in cases if c["p2_action"] != c["act_action"]]
    return {
        "cases_where_p3_differs_from_committed": differ,
        "all_of_them_are_tie_break_cases":
            all(d["corrected"] == d["p3_act"] for d in differ),
        "count": len(differ),
    }


def asking_that_does_not_pay(grid_rows: list) -> dict:
    """Lambdas where P3 chooses to ask and is worse off for it on this case set.

    Noticed after the sweep ran, not predicted, and it is an observation about 100
    labelled cases rather than about the rule: the lookahead is an expectation under
    the belief, and a belief that is wrong can make a question worth buying in
    expectation and wasted in outcome. Recorded here so the mean-cost column of the
    sweep is not read as an endorsement of every lambda at which asking begins.
    """
    base = next(g["mean_realised_real"] for g in grid_rows
                if Fraction(g["lambda"]) == 1)
    worse = [g["lambda"] for g in grid_rows
             if g["measured_asks_real"] > 0 and g["mean_realised_real"] > base]
    return {
        "status": "post-hoc observation, not pre-registered",
        "mean_realised_when_never_asking": base,
        "lambdas_where_asking_costs_more_realised": worse,
        "worst": (max(grid_rows, key=lambda g: g["mean_realised_real"])["lambda"]
                  if worse else None),
    }


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def render(f: dict) -> str:
    o = f["offset_diagnosis"]
    tb = f["tie_break_gap"]
    tb_ids = ", ".join("`" + d["case_id"] + "`"
                       for d in tb["cases_where_p3_differs_from_committed"]) or "none"
    tb_plural = "" if tb["count"] == 1 else "s"
    nearest = " and ".join(str(v) for v in
                           o["nearest_committed_b_h_below_and_above"])
    L = ["# Where a policy that may ask actually starts asking", "",
         "Beliefs, constraints and labels from `results/run.json`, unmodified. The "
         "analytic boundary is read from `results/voi-ceiling.json`, not retyped. "
         "Every quantity below is exact rational arithmetic.", "",
         "## The real menu", "",
         f"At the practitioner's prices ($\\lambda = 1$) P3 asks on "
         f"**{f['at_lambda_1']['measured_asks_real']}** of {f['n_cases']} cases, and "
         f"the oracle version -- which credits a question with the entire cost of "
         f"acting -- asks on **{f['at_lambda_1']['measured_asks_oracle']}**. P3 "
         f"therefore plays P2's action on all "
         f"{f['at_lambda_1']['real_agrees_with_p2_corrected']} cases under the "
         f"corrected tie-break, and on "
         f"{f['at_lambda_1']['real_agrees_with_p2']} of the decisions as committed "
         f"in `run.json`, which was generated under the legacy order and differs on "
         f"{f['tie_break_gap']['count']} case{tb_plural} ({tb_ids}) for that reason "
         f"and no other ({tb['all_of_them_are_tie_break_cases']}). "
         "This is the result, not the absence of one: the lookahead is built, it is "
         "priced against the committed matrix, and it declines to buy.", "",
         "## The switch", "",
         "| | lambda | as decimal |", "| --- | ---: | ---: |",
         f"| analytic boundary (committed) | ${f['analytic_lambda']}$ | "
         f"{f['analytic_lambda_float']:.6f} |",
         f"| oracle switch, measured | ${f['lambda_star_oracle']}$ | "
         f"{f['lambda_star_oracle_float']:.6f} |",
         f"| real switch, measured | ${f['lambda_star_real']}$ | "
         f"{f['lambda_star_real_float']:.6f} |", "",
         f"Attained by `{f['argmax_case_oracle']}` and, for the real arm, by "
         f"`{f['argmax_case_real']}` with `{f['argmax_question']}`.", "",
         "## The offset, and its cause", "",
         f"The oracle switch sits **{o['offset']}** "
         f"({o['offset_float']:.6f}) below the analytic boundary. Cause: "
         f"**{o['cause']}**.", "",
         f"The boundary is attained at $b_h = {o['analytic_optimum_b_h']}$ with all "
         f"readiness mass on hot. Pushing that belief through this script's own "
         f"expected-cost code gives ${o['witness_lambda']}$, which reproduces the "
         f"committed boundary ({o['witness_reproduces_analytic']}) -- so the algebra "
         f"is not where the gap comes from. Every committed $b_h$ lies on the decile "
         f"grid ({o['committed_b_h_all_on_deciles']}) and the boundary's argmax does "
         f"not ({not o['optimum_is_on_the_decile_grid']}), with the nearest "
         f"committed values at {nearest}. The break-even ratio rises to the argmax "
         f"and falls after it, so the best available belief is the decile below.", "",
         "| $b_h$ | cases | best oracle break-even | attained by |",
         "| ---: | ---: | ---: | --- |"]
    for c in f["lambda_curve"]:
        L.append(f"| {c['b_h']} | {c['n_cases']} | ${c['max_lambda']}$ "
                 f"({c['max_lambda_float']:.4f}) | `{c['attained_by']}` |")

    L += ["", "## What each question is worth", "",
          "The largest break-even over the 100 cases, question by question. A "
          "question only ever gets bought below its own number.", "",
          "| question | largest break-even lambda | as decimal |",
          "| --- | ---: | ---: |"]
    for qid, lam in f["lambda_star_by_question"].items():
        L.append(f"| `{qid}` | ${lam}$ | {float(Fraction(lam)):.6f} |")

    L += ["", "## Asking, as the ask row is repriced", "",
          "| lambda | oracle asks | real asks | agrees with P2 | mean realised "
          "(real) | questions used |",
          "| ---: | ---: | ---: | ---: | ---: | --- |"]
    for g in f["sweep"]:
        L.append(f"| {g['lambda_float']:.2f} | {g['measured_asks_oracle']} | "
                 f"{g['measured_asks_real']} | "
                 f"{g['real_agrees_with_p2_corrected']} | "
                 f"{g['mean_realised_real']:.3f} | "
                 f"{', '.join(g['questions_used']) or '--'} |")

    a = f["asking_that_does_not_pay"]
    L += ["", "## Asking that the belief endorses and the outcome does not", "",
          f"_{a['status']}._ Never asking costs "
          f"{a['mean_realised_when_never_asking']:.3f} per case on the labelled set. "
          f"Asking is chosen and costs MORE than that at lambda "
          f"{', '.join(a['lambdas_where_asking_costs_more_realised']) or 'nowhere'}"
          f", worst at {a['worst']}. The lookahead is an expectation under the "
          "belief; where the belief is wrong the question is worth buying and wasted "
          "in outcome, and the two facts are not in conflict."]

    L += ["", "## Checks", ""] + [
        f"- `{k}`: **{v}**" for k, v in f["checks"].items()] + [
        f"- `ec_joint` vs `costs.expected_cost` on {f['joint_check']['comparisons']} "
        f"prior/action pairs: max difference {f['joint_check']['max_abs_difference']}"
        f", agrees **{f['joint_check']['agrees']}**", "",
        "## Pre-registration", "", f"_{f['preregistration_comparison']['status']}_",
        "", "| field | predicted | measured | match |",
        "| --- | --- | --- | :---: |"]
    for k, v in f["preregistration_comparison"]["fields"].items():
        L.append(f"| `{k}` | {v['predicted']} | {v['measured']} | {v['match']} |")
    L += ["", f"All fields match: **{f['preregistration_comparison']['all_match']}**",
          ""]
    return "\n".join(L)

def main() -> int:
    run = json.loads(RUN_PATH.read_text(encoding="utf-8"))
    ceiling = json.loads(CEILING_PATH.read_text(encoding="utf-8"))
    rows = run["rows"]
    analytic = Fraction(ceiling["feasibility"][ANALYTIC_LAMBDA_KEY])

    cases = [per_case(r) for r in rows]
    lam_oracle = max(Fraction(c["lambda_oracle"]) for c in cases)
    lam_real = max(Fraction(c["lambda_real"]) for c in cases)
    argmax_o = max(cases, key=lambda c: Fraction(c["lambda_oracle"]))["case_id"]
    argmax_r = max(cases, key=lambda c: Fraction(c["lambda_real"]))
    per_question = {q.id: str(max(Fraction(c["questions"][q.id]["lambda_star"])
                                 for c in cases)) for q in QUESTIONS}

    grid = [Fraction(k, 100) for k in range(100, -1, -5)]
    grid_rows = sweep(rows, cases, grid)
    one = next(g for g in grid_rows if Fraction(g["lambda"]) == 1)

    findings = {
        "source": "results/run.json (unmodified); analytic boundary from "
                  "results/voi-ceiling.json (unmodified)",
        "n_cases": len(rows),
        "analytic_lambda": str(analytic),
        "analytic_lambda_float": float(analytic),
        "at_lambda_1": one,
        "lambda_star_oracle": str(lam_oracle),
        "lambda_star_oracle_float": float(lam_oracle),
        "lambda_star_real": str(lam_real),
        "lambda_star_real_float": float(lam_real),
        "argmax_case_oracle": argmax_o,
        "argmax_case_real": argmax_r["case_id"],
        "argmax_question": argmax_r["best_question"],
        "lambda_star_by_question": per_question,
        "offset_from_analytic": str(analytic - lam_oracle),
        "lambda_curve": lambda_curve(rows),
        "sweep": grid_rows,
        "tie_break_gap": tie_break_gap(cases),
        "asking_that_does_not_pay": asking_that_does_not_pay(grid_rows),
        "joint_check": joint_agrees_with_expected_cost(rows),
        "cases": cases,
        "preregistration": PREREGISTRATION,
    }
    findings["offset_diagnosis"] = diagnose_offset(rows, analytic, lam_oracle)
    findings["offset_cause"] = findings["offset_diagnosis"]["cause"]
    findings["checks"] = checks(cases, grid_rows, analytic, lam_oracle, lam_real)
    findings["preregistration_comparison"] = compare(findings)

    OUT_JSON.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    OUT_MD.write_text(render(findings), encoding="utf-8")
    print(render(findings))
    print(f"\nwrote {OUT_JSON}\nwrote {OUT_MD}")

    status = 0
    bad = [k for k, v in findings["checks"].items() if not v]
    if bad:
        print(f"\nSTOP: {bad} failed. These are not findings, they are conditions "
              f"for the reported switch points to mean anything.", file=sys.stderr)
        status = 1
    if not findings["joint_check"]["agrees"]:
        print("\nSTOP: ec_joint disagrees with costs.expected_cost on beliefs that "
              "factorise, so every lambda above is computed with the wrong cost "
              "model.", file=sys.stderr)
        status = 1
    if not findings["preregistration_comparison"]["all_match"]:
        print("\nNOTE: the measurement diverged from the pre-registration. That is "
              "reported, not corrected -- see the table above for which field.",
              file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
