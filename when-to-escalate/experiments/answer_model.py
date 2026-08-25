"""
answer_model.py — expected information gain of the Gate 3 question set.

Computes, for each of the four questions in `src.questions` and each of the 100
committed beliefs in `results/run.json`:

    P_b(u)    = sum_s P_b(s) * P(u | s)                 predictive over answers
    b^u(s)    = P_b(s) * P(u | s) / P_b(u)              posterior after answer u
    IG(q | b) = H(b) - sum_u P_b(u) * H(b^u)            Gate 1 definitions, §2

and then runs the pre-registered sensitivity sweep over the answer model's 22 free
parameters.

**This is an illustration, not evidence about `ask`.** Gate 1 §3 proves
`VoI(q | b) <= V_act(b) - EC(ask | b)`, a bound that follows from `V_q(b) >= 0`
alone. It grants a free perfect oracle, so it holds for every question and every
answer model, and its maximum over all beliefs is `-2/13` in closed form
(`results/voi-ceiling.json`). No number this script produces can move that. What
this script does is make the theorem's "every answer model" quantifier concrete by
exhibiting one worked instance with its assumptions written down, and discharge the
adapter OQ1 owes. The sweep measures whether the **information-gain magnitudes**
are stable — the mechanism, not the claim.

One trap this file is built around. `H(b) = H_r(b) + H_h(b)` holds for the prior
because readiness and needs_human are independent by design (locked decision 0a).
It does **not** hold for a posterior that couples them: there `H_r + H_h > H_joint`,
so using the sum for `H(b^u)` would overstate the expected posterior entropy and
therefore understate `IG`. Every entropy below is the **joint** entropy over the six
states; the additive form is asserted on the prior, where it is a theorem, and its
failure on posteriors is measured rather than assumed away.

That failure has an exact name. Writing `R` for readiness, `Hh` for needs_human and
`U` for the answer,

    IG = I(R,Hh ; U) = IG_r + IG_h + I(R ; Hh | U)

where `IG_r`, `IG_h` are the per-axis gains and the third term is the coupling the
answer induces between the axes. It is >= 0, it is zero exactly when no answer
couples them, and it is an independent cross-check on the `separates()` test in
`src.questions`: a separable table must give a coupling term of 0.

Offline and deterministic. **No API calls** — the answer model is a committed table
and the beliefs come from `results/run.json`.

Usage
    python experiments/answer_model.py
    python experiments/answer_model.py --json results/answer-model.json \
                                       --md results/answer-model.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.belief import Belief                                        # noqa: E402
from src.questions import (NEEDS_HUMAN, QUESTIONS, READINESS,        # noqa: E402
                           STATES, SWEEP_CLIP, SWEEP_DELTAS,
                           NonFactorisingError, factorises, narrow,
                           rows_sum_to_one, separates, widen)

RUN_JSON = ROOT / "results" / "run.json"
VOI_JSON = ROOT / "results" / "voi-ceiling.json"

TOL = 1e-12

#: The three questions whose IG ordering the sweep watches. `q_null` is excluded:
#: its IG is identically 0, so including it in an ordering would be meaningless.
REAL = tuple(q.id for q in QUESTIONS if q.id != "q_null")


# --------------------------------------------------------------------------- #
# Entropy — joint, over the six states
# --------------------------------------------------------------------------- #

def entropy(dist) -> float:
    """Shannon entropy in bits of an iterable of probabilities. 0*log0 := 0."""
    total = 0.0
    for p in dist:
        if p > 0.0:
            total -= p * math.log2(p)
    return total


def joint_entropy(joint) -> float:
    return entropy(joint[s] for s in STATES)


def axis_entropies(joint) -> tuple[float, float]:
    """(H_r, H_h) of the marginals of a six-vector."""
    h_r = entropy(sum(joint[(r, h)] for h in NEEDS_HUMAN) for r in READINESS)
    p_true = sum(joint[(r, True)] for r in READINESS)
    h_h = entropy((p_true, 1.0 - p_true))
    return h_r, h_h


# --------------------------------------------------------------------------- #
# One question against one belief
# --------------------------------------------------------------------------- #

def evaluate(question, joint, table=None) -> dict:
    """IG and its decomposition for one question at one belief.

    `table` overrides the question's committed table, which is how the sweep
    perturbs entries without mutating the module constants.
    """
    tab = question.table if table is None else table

    predictive, posteriors = [], []
    for j, _u in enumerate(question.answers):
        weights = {s: joint[s] * tab[s][j] / 100.0 for s in STATES}
        p_u = sum(weights.values())
        predictive.append(p_u)
        posteriors.append({s: (weights[s] / p_u if p_u > 0.0 else 0.0)
                           for s in STATES})

    h_prior = joint_entropy(joint)
    hr_prior, hh_prior = axis_entropies(joint)

    exp_post = sum(p * joint_entropy(post)
                   for p, post in zip(predictive, posteriors) if p > 0.0)
    exp_post_r = 0.0
    exp_post_h = 0.0
    coupling = 0.0
    n_coupled = 0
    for p, post in zip(predictive, posteriors):
        if p <= 0.0:
            continue
        hr, hh = axis_entropies(post)
        exp_post_r += p * hr
        exp_post_h += p * hh
        # I(R ; Hh | U = u) = H_r + H_h - H_joint, >= 0, zero iff independent
        coupling += p * (hr + hh - joint_entropy(post))
        if not factorises(post, tol=TOL):
            n_coupled += 1

    ig = h_prior - exp_post
    return {
        "h_prior_joint": h_prior,
        "h_prior_readiness": hr_prior,
        "h_prior_needs_human": hh_prior,
        "additivity_residual": abs(h_prior - (hr_prior + hh_prior)),
        "predictive": {u: p for u, p in zip(question.answers, predictive)},
        "predictive_sums_to_1_residual": abs(sum(predictive) - 1.0),
        "expected_posterior_entropy": exp_post,
        "ig": ig,
        "ig_readiness": hr_prior - exp_post_r,
        "ig_needs_human": hh_prior - exp_post_h,
        "coupling_term": coupling,
        "n_answers_with_coupled_posterior": n_coupled,
        # IG = IG_r + IG_h + coupling, exactly. Residual is the arithmetic check.
        "decomposition_residual": abs(
            ig - ((hr_prior - exp_post_r) + (hh_prior - exp_post_h) + coupling)),
    }


# --------------------------------------------------------------------------- #
# The 100 committed beliefs
# --------------------------------------------------------------------------- #

def load_rows() -> list[dict]:
    return json.loads(RUN_JSON.read_text())["rows"]


def per_case(rows: list[dict]) -> dict:
    out = []
    for row in rows:
        b = Belief.from_dict(row["belief"])
        joint = widen(b.readiness, b.needs_human)
        rec = {
            "case_id": row["case_id"],
            "archetype": row["archetype"],
            "split": row["split"],
            "b_h": b.needs_human,
            "h_joint": joint_entropy(joint),
            "questions": {},
        }
        for q in QUESTIONS:
            rec["questions"][q.id] = evaluate(q, joint)
        out.append(rec)

    summary = {}
    for q in QUESTIONS:
        vals = [c["questions"][q.id]["ig"] for c in out]
        coup = [c["questions"][q.id]["coupling_term"] for c in out]
        n_coupled_cases = sum(
            1 for c in out if c["questions"][q.id]["n_answers_with_coupled_posterior"])
        best = max(out, key=lambda c: c["questions"][q.id]["ig"])
        summary[q.id] = {
            "target": q.target,
            "separable_table": separates(q),
            "mean_ig_bits": sum(vals) / len(vals),
            "min_ig_bits": min(vals),
            "max_ig_bits": max(vals),
            "max_ig_case": best["case_id"],
            "mean_coupling_bits": sum(coup) / len(coup),
            "max_coupling_bits": max(coup),
            "n_cases_with_any_coupled_posterior": n_coupled_cases,
            "n_cases_ig_below_0.01_bits": sum(1 for v in vals if v < 0.01),
        }
    return {"n": len(out), "by_question": summary, "cases": out}


# --------------------------------------------------------------------------- #
# Invariants — the five in the pre-registration, plus the decomposition
# --------------------------------------------------------------------------- #

def check_invariants(detail: dict) -> dict:
    cases = detail["cases"]
    checks = {
        "ig_non_negative": [],
        "q_null_ig_is_zero": [],
        "predictive_sums_to_one": [],
        "ig_at_most_h_prior": [],
        "prior_entropy_is_additive": [],
        "decomposition_exact": [],
        "coupling_non_negative": [],
        "separable_table_has_zero_coupling": [],
    }
    for c in cases:
        for qid, r in c["questions"].items():
            key = f"{c['case_id']}/{qid}"
            if r["ig"] < -TOL:
                checks["ig_non_negative"].append(key)
            if qid == "q_null" and abs(r["ig"]) > TOL:
                checks["q_null_ig_is_zero"].append(key)
            if r["predictive_sums_to_1_residual"] > TOL:
                checks["predictive_sums_to_one"].append(key)
            if r["ig"] > r["h_prior_joint"] + TOL:
                checks["ig_at_most_h_prior"].append(key)
            if r["additivity_residual"] > TOL:
                checks["prior_entropy_is_additive"].append(key)
            if r["decomposition_residual"] > TOL:
                checks["decomposition_exact"].append(key)
            if r["coupling_term"] < -TOL:
                checks["coupling_non_negative"].append(key)
            if separates(next(q for q in QUESTIONS if q.id == qid)) \
                    and r["coupling_term"] > TOL:
                checks["separable_table_has_zero_coupling"].append(key)

    n = len(cases)
    # IG is a mutual information, so it is >= 0 in exact arithmetic. In floats it
    # can land a few units in the last place below zero on a case where the true
    # value is exactly 0 (a degenerate belief, or q_null). Reported rather than
    # clamped, so a real sign error could not hide inside the tolerance.
    most_negative = min(
        (r["ig"] for c in cases for r in c["questions"].values()), default=0.0)
    return {
        "n_cases": n,
        "n_question_case_pairs": n * len(QUESTIONS),
        "violations": {k: v for k, v in checks.items()},
        "all_hold": all(not v for v in checks.values()),
        "most_negative_ig_seen": most_negative,
        "most_negative_ig_is_float_noise": abs(most_negative) < TOL,
        "table_rows_sum_to_one": {q.id: rows_sum_to_one(q) for q in QUESTIONS},
    }


def free_check(detail: dict) -> dict:
    """The entropy cases the data hands over, named in the pre-registration §6.

    Four beliefs sit at b_h = 0.0 exactly, so H_h = 0 and no answer can reduce it.
    One of them, a11-repeated-097, additionally has a degenerate readiness belief,
    so H(b) = 0 on both axes and IG must be 0 for every question. It fails loudly
    if the entropy code has a sign or normalisation error.
    """
    by_id = {c["case_id"]: c for c in detail["cases"]}
    named = ["a08-reaction-075", "a08-reaction-077", "a11-first-095",
             "a11-repeated-097"]
    out = {}
    for cid in named:
        c = by_id.get(cid)
        if c is None:
            out[cid] = {"present": False}
            continue
        anyq = next(iter(c["questions"].values()))
        out[cid] = {
            "present": True,
            "b_h": c["b_h"],
            "h_needs_human": anyq["h_prior_needs_human"],
            "h_readiness": anyq["h_prior_readiness"],
            "h_joint": c["h_joint"],
            "ig_by_question": {q: r["ig"] for q, r in c["questions"].items()},
            "ig_needs_human_by_question": {q: r["ig_needs_human"]
                                           for q, r in c["questions"].items()},
        }
    zero = out.get("a11-repeated-097", {})
    return {
        "cases": out,
        "degenerate_case": "a11-repeated-097",
        "degenerate_h_joint": zero.get("h_joint"),
        "degenerate_all_ig_zero": (
            all(abs(v) <= TOL for v in zero.get("ig_by_question", {}).values())
            if zero.get("present") else None),
        "b_h_zero_cases_have_zero_h_h": all(
            abs(v["h_needs_human"]) <= TOL for v in out.values() if v.get("present")),
        "b_h_zero_cases_have_zero_ig_h": all(
            abs(x) <= TOL for v in out.values() if v.get("present")
            for x in v["ig_needs_human_by_question"].values()),
    }


# --------------------------------------------------------------------------- #
# The adapter — both directions, per OQ1
# --------------------------------------------------------------------------- #

def adapter_check(rows: list[dict]) -> dict:
    """Round-trip every prior; find a real coupled posterior and confirm it raises.

    The happy path alone would pass on an adapter that always projects, so the
    raising path is checked on a posterior that actually arose in the run rather
    than on a hand-built example.
    """
    worst_round_trip = 0.0
    for row in rows:
        b = Belief.from_dict(row["belief"])
        joint = widen(b.readiness, b.needs_human)
        r2, h2 = narrow(joint)
        worst_round_trip = max(
            worst_round_trip,
            max(abs(r2[k] - b.readiness[k]) for k in READINESS),
            abs(h2 - b.needs_human))

    found = None
    raised = None
    for row in rows:
        b = Belief.from_dict(row["belief"])
        joint = widen(b.readiness, b.needs_human)
        for q in QUESTIONS:
            for j, u in enumerate(q.answers):
                w = {s: joint[s] * q.table[s][j] / 100.0 for s in STATES}
                p_u = sum(w.values())
                if p_u <= 0.0:
                    continue
                post = {s: w[s] / p_u for s in STATES}
                if not factorises(post, tol=TOL):
                    found = {"case_id": row["case_id"], "question": q.id,
                             "answer": u, "p_u": p_u,
                             "posterior": {f"{r}|{h}": post[(r, h)]
                                           for r, h in STATES}}
                    try:
                        narrow(post)
                        raised = False
                    except NonFactorisingError as exc:
                        raised = True
                        found["error"] = str(exc)
                    break
            if found:
                break
        if found:
            break

    return {
        "prior_round_trip_max_error": worst_round_trip,
        "prior_round_trip_within_1e_12": worst_round_trip < TOL,
        "found_a_real_coupled_posterior": found is not None,
        "coupled_example": found,
        "narrow_raised_on_it": raised,
        "belief_class_unmodified": sorted(Belief.__dataclass_fields__) ==
                                   ["needs_human", "readiness"],
    }


# --------------------------------------------------------------------------- #
# The sweep — 22 free parameters, four deltas each
# --------------------------------------------------------------------------- #

def _distinct_rows(question) -> list[tuple[tuple[int, ...], list]]:
    """The question's distinct rows and the states each covers.

    The axis-only questions repeat a row across the other axis, and perturbing a
    single state's entry would break that structure — it would change the
    question's character, not just its numbers. So the sweep's unit is the
    distinct row, which is why the free-parameter count is 22 and not 54.
    """
    groups: dict[tuple[int, ...], list] = {}
    for s in STATES:
        groups.setdefault(question.table[s], []).append(s)
    return list(groups.items())


def _perturb(row: tuple[int, ...], j: int, delta: float) -> tuple[tuple[int, ...], bool]:
    """Move entry `j` by `delta`, clip it, rescale the rest to restore sum 1.

    Returns the perturbed row and whether the clip bound bit. Entries come back as
    floats out of 100 rather than integers: a 0.05 shift followed by renormalisation
    does not generally land on a whole percent, and rounding it to one would silently
    alter the perturbation being reported.
    """
    lo, hi = SWEEP_CLIP
    target = row[j] / 100.0 + delta
    clipped = min(hi, max(lo, target))
    was_clipped = abs(clipped - target) > 1e-15

    rest = [row[k] / 100.0 for k in range(len(row)) if k != j]
    rest_sum = sum(rest)
    scale = (1.0 - clipped) / rest_sum if rest_sum > 0 else 0.0
    out = []
    ri = 0
    for k in range(len(row)):
        if k == j:
            out.append(clipped * 100.0)
        else:
            out.append(rest[ri] * scale * 100.0)
            ri += 1
    return tuple(out), was_clipped


def sweep(rows: list[dict], baseline: dict) -> dict:
    joints = []
    for row in rows:
        b = Belief.from_dict(row["belief"])
        joints.append(widen(b.readiness, b.needs_human))

    base_mean = {qid: baseline["by_question"][qid]["mean_ig_bits"] for qid in REAL}
    base_order = sorted(REAL, key=lambda q: -base_mean[q])
    base_per_case = [
        sorted(REAL, key=lambda q: -c["questions"][q]["ig"])
        for c in baseline["cases"]
    ]

    variants = []
    n_clipped = 0
    min_entry_seen = 1.0
    for q in QUESTIONS:
        if q.id == "q_null":
            continue                       # the control is not a free parameter
        for row_values, states in _distinct_rows(q):
            for j, u in enumerate(q.answers):
                if u == "no_answer":
                    continue               # absorbs the renormalisation
                for delta in SWEEP_DELTAS:
                    new_row, clipped = _perturb(row_values, j, delta)
                    n_clipped += int(clipped)
                    min_entry_seen = min(min_entry_seen, min(new_row) / 100.0)
                    table = dict(q.table)
                    for s in states:
                        table[s] = new_row

                    means = {}
                    per_case_orders = []
                    for idx, joint in enumerate(joints):
                        vals = {}
                        for qq in QUESTIONS:
                            if qq.id == "q_null":
                                continue
                            t = table if qq.id == q.id else None
                            vals[qq.id] = evaluate(qq, joint, table=t)["ig"]
                        per_case_orders.append(
                            sorted(REAL, key=lambda k: -vals[k]))
                        for k, v in vals.items():
                            means[k] = means.get(k, 0.0) + v / len(joints)

                    order = sorted(REAL, key=lambda k: -means[k])
                    same_per_case = sum(
                        1 for a, b_ in zip(per_case_orders, base_per_case) if a == b_)
                    variants.append({
                        "question": q.id,
                        "row_states": [f"{r}|{h}" for r, h in states],
                        "answer": u,
                        "delta": delta,
                        "clipped": clipped,
                        "min_entry_after_renormalisation": min(new_row) / 100.0,
                        "mean_ig": means,
                        "mean_ig_shift": {k: means[k] - base_mean[k] for k in REAL},
                        "order": order,
                        "order_matches_baseline": order == base_order,
                        "n_cases_with_baseline_order": same_per_case,
                    })

    flips = [v for v in variants if not v["order_matches_baseline"]]
    small = [v for v in variants if abs(v["delta"]) == 0.05]
    small_flips = [v for v in small if not v["order_matches_baseline"]]
    worst_shift = max(
        (abs(s) for v in variants for s in v["mean_ig_shift"].values()), default=0.0)

    # Post-hoc diagnosis. It does NOT change the pre-registered verdict below —
    # §5 fixed the decision rule as "does the ordering flip at +/-0.05", and it
    # does. This block reports WHY, because "too fragile" without a magnitude is
    # not a usable finding.
    #
    # The comparison that matters: how far one perturbation moves a single
    # question's mean IG, against how far apart the three questions are to begin
    # with. If the former exceeds the latter, the sweep was being asked to resolve
    # a signal smaller than its own step size.
    spread = max(base_mean.values()) - min(base_mean.values())
    by_delta = {}
    for dl in sorted({abs(d) for d in SWEEP_DELTAS}):
        vs = [v for v in variants if abs(v["delta"]) == dl]
        fl = [v for v in vs if not v["order_matches_baseline"]]
        shifts = [abs(x) for v in vs for x in v["mean_ig_shift"].values()]
        margins = []
        for v in fl:
            ranked = sorted(v["mean_ig"].values(), reverse=True)
            margins.append(ranked[0] - ranked[1])
        by_delta[f"{dl:.2f}"] = {
            "n_variants": len(vs),
            "n_flips": len(fl),
            "max_abs_mean_ig_shift_bits": max(shifts) if shifts else 0.0,
            "min_post_flip_top_margin_bits": min(margins) if margins else None,
            "max_post_flip_top_margin_bits": max(margins) if margins else None,
            "n_flips_decided_by_over_0.002_bits": sum(1 for m in margins if m > 0.002),
        }

    return {
        "grid": {"deltas": list(SWEEP_DELTAS), "clip": list(SWEEP_CLIP),
                 "unit": "distinct table row, non-no_answer entry, one at a time",
                 "renormalisation": "Perturbed entry clipped, remaining entries "
                                    "rescaled so the row sums to 1"},
        "n_free_parameters": len(variants) // len(SWEEP_DELTAS),
        "n_variants": len(variants),
        "n_clipped": n_clipped,
        "min_entry_after_renormalisation": min_entry_seen,
        "baseline_mean_ig": base_mean,
        "baseline_order": base_order,
        "n_order_flips": len(flips),
        "n_order_flips_at_0.05": len(small_flips),
        "flips": [{k: v[k] for k in ("question", "answer", "delta", "order")}
                  for v in flips],
        "max_abs_mean_ig_shift_bits": worst_shift,
        "min_cases_holding_baseline_order": min(
            (v["n_cases_with_baseline_order"] for v in variants), default=None),
        "diagnosis": {
            "post_hoc": True,
            "changes_the_verdict": False,
            "baseline_spread_bits": spread,
            "by_delta": by_delta,
            "perturbation_exceeds_the_spread_it_must_resolve": (
                by_delta["0.05"]["max_abs_mean_ig_shift_bits"] > spread),
            "reading": (
                "The three questions' mean IGs span "
                f"{spread:.4f} bits, while a single +/-0.05 perturbation of one "
                "entry moves one question's mean IG by up to "
                f"{by_delta['0.05']['max_abs_mean_ig_shift_bits']:.4f} bits. The "
                "ordering test was asking the sweep to resolve a signal smaller "
                "than its own step size, so the flips are decisive re-orderings "
                "rather than fourth-decimal ties: "
                f"{by_delta['0.05']['n_flips_decided_by_over_0.002_bits']} of "
                f"{by_delta['0.05']['n_flips']} flips at +/-0.05 leave the new "
                "winner ahead by more than 0.002 bits."),
            "grid_limitation": (
                "The grid was pre-registered in absolute probability units and "
                "never checked against the spread of the quantity being ordered. "
                "An absolute 0.10 is 14% of a 0.70 entry and 100% of a 0.10 entry, "
                "so one grid is a mild and a total perturbation depending on where "
                "it lands. Same shape of blind spot as the Gate 2 count threshold "
                "that was not scale-free. The grid is NOT changed and the sweep is "
                "NOT re-run on a different one: §5 pre-registered this decision "
                "rule and repairing the test after seeing it fail is the thing "
                "pre-registration exists to prevent."),
        },
        # Pre-registered reading, §5. Stated here so the JSON carries the verdict
        # rather than leaving it to be narrated afterwards.
        "verdict": ("mechanism locally stable: the IG ordering of the three real "
                    "questions is unchanged under every perturbation"
                    if not flips else
                    ("answer model too fragile to illustrate anything: the ordering "
                     "flips under a +/-0.05 perturbation, so the illustration is "
                     "withdrawn rather than repaired by choosing better entries"
                     if small_flips else
                     "ordering survives every +/-0.05 perturbation but flips at "
                     "+/-0.10; reported as a partial stability result")),
        "measures": "stability of the information-gain magnitudes (the mechanism)",
        "does_not_measure": ("the impossibility result, which is answer-model-free "
                             "and cannot be defended or undermined by this sweep"),
        "variants": variants,
    }


# --------------------------------------------------------------------------- #

def voi_context() -> dict:
    """The ceiling this gate cannot move, quoted from its own result file."""
    if not VOI_JSON.exists():
        return {"available": False}
    v = json.loads(VOI_JSON.read_text())
    g = v.get("global_ceiling", {})
    return {
        "available": True,
        "source": str(VOI_JSON.relative_to(ROOT)),
        "max_ceiling_exact": g.get("ceiling_exact"),
        "max_ceiling_float": g.get("ceiling_float"),
        "answer_model_free": True,
        "note": ("IG is in bits and the ceiling is in cost points. No IG value in "
                 "this file enters that bound, which grants a free perfect oracle "
                 "and so already assumed the best possible answer model."),
    }


def render_md(findings: dict) -> str:
    d, s = findings["per_case"], findings["sweep"]
    inv, fc, ad = findings["invariants"], findings["free_check"], findings["adapter"]
    v = findings["voi_context"]
    L = []
    a = L.append

    a("# Expected information gain of the Gate 3 question set")
    a("")
    a("An **illustration** of the answer model locked in "
      "`decisions/v2-gate3-preregistration.md`, computed by "
      "`experiments/answer_model.py` over the "
      f"{d['n']} beliefs in `results/run.json`. Offline, no API calls.")
    a("")
    a("**It is not evidence about `ask`.** The impossibility result is "
      "answer-model-free: `VoI(q | b) <= V_act(b) - EC(ask | b)` follows from "
      "`V_q(b) >= 0` alone, grants a free perfect oracle, and so holds for every "
      "answer model.")
    if v.get("available"):
        a(f"Its maximum over all beliefs is `{v['max_ceiling_exact']}` = "
          f"{v['max_ceiling_float']:+.6f} ({v['source']}). Nothing below moves it.")
    a("")
    a("## Information gain per question")
    a("")
    a("Mean and range over the 100 beliefs. `IG` is in bits; the belief's own "
      "entropy is at most 2.585 bits.")
    a("")
    a("| question | targets | table separable | mean IG | min | max | max at | "
      "cases with IG < 0.01 |")
    a("| --- | --- | --- | ---: | ---: | ---: | --- | ---: |")
    for qid, r in d["by_question"].items():
        a(f"| `{qid}` | {r['target']} | {r['separable_table']} | "
          f"{r['mean_ig_bits']:.4f} | {r['min_ig_bits']:.4f} | "
          f"{r['max_ig_bits']:.4f} | `{r['max_ig_case']}` | "
          f"{r['n_cases_ig_below_0.01_bits']} |")
    a("")
    a("`q_null` is the control. Its answer cannot depend on the state, so its IG is "
      "0 by the equality case in the Gate 1 definitions — an executed assertion, "
      "not a claim in prose.")
    a("")
    a(f"A `-0.0000` in the min column is float noise, not a negative mutual "
      f"information: the most negative IG anywhere in the "
      f"{inv['n_question_case_pairs']} pairs is "
      f"{inv['most_negative_ig_seen']:.2e}, which is float rounding on a case whose "
      f"true value is exactly 0. Reported rather than clamped, so a real sign error "
      f"could not hide inside the tolerance.")
    a("")
    a("## How much each answer couples the two axes")
    a("")
    a("`IG = IG_r + IG_h + I(R ; Hh | U)`, exactly. The third term is the coupling "
      "the answer induces between readiness and needs_human, and it is what makes "
      "the OQ1 six-vector necessary: a coupled posterior does not fit in a "
      "`Belief`.")
    a("")
    a("| question | mean coupling (bits) | max | cases with a coupled posterior |")
    a("| --- | ---: | ---: | ---: |")
    for qid, r in d["by_question"].items():
        a(f"| `{qid}` | {r['mean_coupling_bits']:.6f} | "
          f"{r['max_coupling_bits']:.6f} | "
          f"{r['n_cases_with_any_coupled_posterior']} |")
    a("")
    a("The three separable questions sit at 0 up to float noise — a printed "
      "`-0.000000` is a value of magnitude below 1e-15, not a negative mutual "
      "information. The `separable table has zero coupling` invariant below pins "
      "it against the tolerance, and it is an independent cross-check on "
      "`separates()`: that is a rank-1 test on the table, this is an entropy "
      "computed from the posteriors, so their agreement is evidence rather than "
      "tautology.")
    a("")
    a("## The adapter, both directions")
    a("")
    a(f"- Every one of the {d['n']} priors round-trips `Belief -> six-vector -> "
      f"Belief` to within {ad['prior_round_trip_max_error']:.2e}.")
    if ad["found_a_real_coupled_posterior"]:
        e = ad["coupled_example"]
        a(f"- A coupled posterior does arise in the run: `{e['case_id']}`, "
          f"`{e['question']}`, answer `{e['answer']}` (P = {e['p_u']:.4f}). "
          f"`narrow()` raised on it: **{ad['narrow_raised_on_it']}**.")
    else:
        a("- No coupled posterior arose on these 100 beliefs, so the raising path "
          "is exercised only by the unit test.")
    a(f"- `Belief` is unmodified: fields are still "
      f"{sorted(Belief.__dataclass_fields__)}.")
    a("")
    a("## Sweep")
    a("")
    a(f"{s['n_free_parameters']} free parameters x {len(s['grid']['deltas'])} "
      f"deltas = {s['n_variants']} variants. Unit: {s['grid']['unit']}. "
      f"{s['grid']['renormalisation']}.")
    a("")
    a(f"- Baseline ordering by mean IG: "
      + " > ".join(f"`{q}`" for q in s["baseline_order"]))
    a(f"- Order flips: **{s['n_order_flips']}** of {s['n_variants']} "
      f"({s['n_order_flips_at_0.05']} at +/-0.05)")
    a(f"- Largest shift in any mean IG: {s['max_abs_mean_ig_shift_bits']:.4f} bits")
    a(f"- Entries clipped to {s['grid']['clip']}: {s['n_clipped']}; "
      f"smallest entry after renormalisation "
      f"{s['min_entry_after_renormalisation']:.4f}")
    a(f"- Fewest cases holding the baseline per-case ordering: "
      f"{s['min_cases_holding_baseline_order']} of {d['n']}")
    a("")
    a(f"**Pre-registered verdict:** {s['verdict']}.")
    a("")
    a(f"This measures {s['measures']}. It does **not** measure "
      f"{s['does_not_measure']}.")
    a("")
    g = s["diagnosis"]
    a("### Why it is fragile — post-hoc diagnosis, which does not change the verdict")
    a("")
    a("| delta | variants | flips | max shift in one mean IG | flips won by "
      "> 0.002 bits |")
    a("| ---: | ---: | ---: | ---: | ---: |")
    for dl, r in g["by_delta"].items():
        a(f"| ±{dl} | {r['n_variants']} | {r['n_flips']} | "
          f"{r['max_abs_mean_ig_shift_bits']:.4f} | "
          f"{r['n_flips_decided_by_over_0.002_bits']} |")
    a("")
    a(g["reading"])
    a("")
    a("So the flips are not an artifact of a near-tie. " + g["grid_limitation"])
    a("")
    a("### What the withdrawal does and does not cover")
    a("")
    a("Withdrawn: any claim that the IG ordering of these three questions means "
      "something, and any use of these IG magnitudes as a stable illustration.")
    a("")
    a("Not affected, because the sweep does not bear on them:")
    a("")
    a("- The invariants above. They are properties of the implementation against "
      "the Gate 1 definitions, and hold for any table.")
    a("- The OQ1 adapter, discharged on a coupled posterior that actually arose.")
    a("- The impossibility result, which is answer-model-free.")
    a("")
    a("## Invariants")
    a("")
    a(f"All {inv['n_question_case_pairs']} question-case pairs checked.")
    a("")
    a("| invariant | violations |")
    a("| --- | ---: |")
    for k, bad in inv["violations"].items():
        a(f"| {k.replace('_', ' ')} | {len(bad)} |")
    a("")
    a("### The free check the data hands over")
    a("")
    a("Four beliefs sit at `b_h = 0.0` exactly, so `H_h = 0` and no answer can "
      "reduce it. One, `a11-repeated-097`, also has a degenerate readiness belief, "
      "so `H(b) = 0` on both axes and IG must be 0 for every question.")
    a("")
    a("| case | b_h | H_r | H_h | H joint | max IG over Q |")
    a("| --- | ---: | ---: | ---: | ---: | ---: |")
    for cid, c in fc["cases"].items():
        if not c.get("present"):
            a(f"| `{cid}` | absent | | | | |")
            continue
        a(f"| `{cid}` | {c['b_h']:.2f} | {c['h_readiness']:.4f} | "
          f"{c['h_needs_human']:.4f} | {c['h_joint']:.4f} | "
          f"{max(c['ig_by_question'].values()):.6f} |")
    a("")
    a(f"- `H_h = 0` on all four: **{fc['b_h_zero_cases_have_zero_h_h']}**")
    a(f"- `IG_h = 0` on all four, every question: "
      f"**{fc['b_h_zero_cases_have_zero_ig_h']}**")
    a(f"- `IG = 0` for every question on `{fc['degenerate_case']}`: "
      f"**{fc['degenerate_all_ig_zero']}**")
    a("")
    a("## What this does not establish")
    a("")
    a("- The answer model is **not validated**. Nothing in the data can confirm "
      "these numbers are right; the cases are single messages with no answers to "
      "fit to.")
    a("- The 22 free parameters are **(AI-proposed, Kaps-reviewed)**, not "
      "practitioner-set.")
    a("- A1 (the answer depends on the state, not the message) is false in detail "
      "and accepted for the reason given in the pre-registration.")
    a("- No claim about `ask` follows from any number here.")
    a("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="write the raw findings here")
    ap.add_argument("--md", type=Path, help="write the rendered report here")
    args = ap.parse_args()

    rows = load_rows()
    detail = per_case(rows)
    findings = {
        "n_cases": detail["n"],
        "source": str(RUN_JSON.relative_to(ROOT)),
        "is_an_illustration": True,
        "voi_context": voi_context(),
        "per_case": detail,
        "invariants": check_invariants(detail),
        "free_check": free_check(detail),
        "adapter": adapter_check(rows),
        "sweep": sweep(rows, detail),
    }

    d = findings["per_case"]
    print(f"\n=== Information gain, {d['n']} committed beliefs ===")
    print(f"{'question':14s} {'sep':>5s} {'mean IG':>9s} {'min':>8s} {'max':>8s} "
          f"{'mean coup':>10s} {'coupled':>8s}")
    for qid, r in d["by_question"].items():
        print(f"{qid:14s} {str(r['separable_table']):>5s} "
              f"{r['mean_ig_bits']:9.4f} {r['min_ig_bits']:8.4f} "
              f"{r['max_ig_bits']:8.4f} {r['mean_coupling_bits']:10.6f} "
              f"{r['n_cases_with_any_coupled_posterior']:8d}")

    inv = findings["invariants"]
    print(f"\n=== Invariants ({inv['n_question_case_pairs']} question-case pairs) ===")
    for k, bad in inv["violations"].items():
        print(f"  {k:38s} violations: {len(bad)}"
              + (f"  {bad[:3]}" if bad else ""))
    print(f"  all hold: {inv['all_hold']}")

    fc = findings["free_check"]
    print("\n=== Free check ===")
    print(f"  H_h = 0 on the four b_h=0 cases: {fc['b_h_zero_cases_have_zero_h_h']}")
    print(f"  IG_h = 0 there for every question: "
          f"{fc['b_h_zero_cases_have_zero_ig_h']}")
    print(f"  {fc['degenerate_case']}: H(b) = {fc['degenerate_h_joint']:.6f}, "
          f"IG = 0 for every question: {fc['degenerate_all_ig_zero']}")

    ad = findings["adapter"]
    print("\n=== OQ1 adapter ===")
    print(f"  prior round-trip max error {ad['prior_round_trip_max_error']:.2e} "
          f"(within 1e-12: {ad['prior_round_trip_within_1e_12']})")
    print(f"  a real coupled posterior arose: "
          f"{ad['found_a_real_coupled_posterior']}")
    if ad["coupled_example"]:
        e = ad["coupled_example"]
        print(f"    {e['case_id']} / {e['question']} / answer {e['answer']} "
              f"(P={e['p_u']:.4f}); narrow() raised: {ad['narrow_raised_on_it']}")
    print(f"  Belief unmodified: {ad['belief_class_unmodified']}")

    s = findings["sweep"]
    print(f"\n=== Sweep: {s['n_free_parameters']} free parameters, "
          f"{s['n_variants']} variants ===")
    print(f"  baseline order by mean IG: {' > '.join(s['baseline_order'])}")
    print(f"  baseline means: "
          + "  ".join(f"{k}={v:.4f}" for k, v in s["baseline_mean_ig"].items()))
    print(f"  order flips: {s['n_order_flips']} "
          f"({s['n_order_flips_at_0.05']} at +/-0.05)")
    print(f"  largest mean-IG shift: {s['max_abs_mean_ig_shift_bits']:.4f} bits")
    print(f"  clipped entries: {s['n_clipped']}; smallest entry after "
          f"renormalisation {s['min_entry_after_renormalisation']:.4f}")
    print(f"  fewest cases holding baseline per-case order: "
          f"{s['min_cases_holding_baseline_order']}/{d['n']}")
    print(f"  VERDICT: {s['verdict']}")
    g = s["diagnosis"]
    print(f"\n  --- post-hoc diagnosis (does not change the verdict) ---")
    print(f"  baseline spread across the three questions: "
          f"{g['baseline_spread_bits']:.4f} bits")
    for dl, r in g["by_delta"].items():
        print(f"  +/-{dl}: {r['n_flips']:2d}/{r['n_variants']} flips, "
              f"max shift {r['max_abs_mean_ig_shift_bits']:.4f} bits, "
              f"{r['n_flips_decided_by_over_0.002_bits']} won by > 0.002 bits")
    print(f"  a single +/-0.05 perturbation exceeds the spread it must resolve: "
          f"{g['perturbation_exceeds_the_spread_it_must_resolve']}")

    if args.json:
        args.json.write_text(json.dumps(findings, indent=2, default=str))
        print(f"\nwrote {args.json}")
    if args.md:
        args.md.write_text(render_md(findings))
        print(f"wrote {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
