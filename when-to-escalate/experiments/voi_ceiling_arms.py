#!/usr/bin/env python3
"""
The answer-model-free ceiling on all four belief arms, and the calibration floor.

Gate 1 computed the ceiling on one belief set: the beliefs `results/run.json`
recorded. The obvious objection is that those beliefs were the ones a later gate
showed to be poorly calibrated, so the impossibility result might be an artifact of
bad beliefs rather than of the cost matrix. This script answers that objection by
computing the same checks on four belief sets that differ in exactly one variable
at a time:

    published    results/run.json, unchanged — Gate 1's beliefs
    rebaselined  fresh readiness + the fresh written digit
    raw          fresh readiness + the raw elicited log-prob score
    calibrated   fresh readiness + the isotonic-calibrated score

The answer splits in two, and the split is the point.

The closed-form half of the ceiling does not depend on beliefs at all. `V_act(b)`
is capped by `min(alpha*b_h, nu*(1-b_h))` for every belief, and `EC(ask | b)` is
readiness-flat, so `max_b [V_act(b) - EC(ask|b)]` is a property of the cost matrix
and nothing else. Recalibration cannot move it: any belief is still a belief, and
the maximum over all beliefs is already negative. On the unconstrained action menu,
therefore, "the impossibility survives recalibration" is ANALYTIC — a restatement
of the Gate 1 algebra, not a measurement. This script asserts that identity across
the four arms rather than presenting it as a finding, and refuses to run if the
belief-independent sections ever disagree between arms.

What is empirical is narrower: whether any real case reaches the positive-VoI
region that the constrained menu opens up. That region exists (removing `answer`
removes the alpha*b_h half of the cap), and it is `b_h < 1/5` on the ray where the
constrained maximum sits. Whether a case lands there is a fact about beliefs.

Section 3 is the result Gate 4 exists to state. The committed isotonic map has a
floor: its image is bounded below by the lowest pooled PAVA block's positive rate,
6/23 = 0.260870. Both thresholds that matter sit underneath it:

    1/5 = 0.200000  <  3/13 = 0.230769  <  6/23 = 0.260870
    positive-VoI       answer/notify       the map's floor
    region bound       crossover t*

So under the committed calibration no belief can reach the positive-VoI region and
no belief can make `answer` the cheapest action — not because the data happens to
fall that way, but because the map cannot emit a number that low. A calibration map
has a reachable range; a fixed-threshold decision rule has thresholds; cross-entropy
never checks that the thresholds sit inside the range.

The zero-`answer` consequence is already visible in `results/rebaseline.json`'s
committed action counts, so section 4 treats it as a regression guard rather than as
an open test, and says so.

Reads only committed artifacts. Never calls a provider.

    python experiments/voi_ceiling_arms.py
    python experiments/voi_ceiling_arms.py --json results/voi-ceiling-arms.json \
                                           --md results/voi-ceiling-arms.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VOI_CEILING = ROOT / "experiments" / "voi_ceiling.py"
CASES_JSON = ROOT / "data" / "cases.json"
ELICIT_JSON = ROOT / "results" / "logprob-elicitation.json"
REBASELINE_JSON = ROOT / "results" / "rebaseline.json"

#: The claim split. Selection happened on dev, so dev numbers are in-sample and are
#: labelled as such wherever they appear. All 100 cases are computed either way —
#: an arm is never narrowed to the split that suits it.
CLAIM_SPLIT = "test"

#: Sections of `build_findings` that read no beliefs. Asserted by signature in
#: tests/test_voi_ceiling_arms.py and by value here.
BELIEF_INDEPENDENT = ("cost_matrix_constants", "global_ceiling", "witness_crosscheck",
                      "grid_crosscheck", "feasibility", "lambda_crosscheck")

#: Sections that do read beliefs. `constrained_regime` is split: its maximum is a
#: maximum over the whole simplex and is belief-independent; only the two fields
#: naming real cases move with the arm.
BELIEF_DEPENDENT = ("per_case", "invariants")
CONSTRAINED_REGIME_BELIEF_DEPENDENT = ("min_b_h_among_those_cases",
                                       "any_such_case_inside_the_region")

#: The three rationals section 3 lines up. Exact, because the whole claim is an
#: ordering of three numbers within 0.03 of each other and floats would blur it.
POSITIVE_VOI_BOUND = Fraction(1, 5)     # constrained-menu region, on the argmax ray
T_STAR = Fraction(3, 13)                # nu/(alpha+nu), the answer/notify crossover
ISOTONIC_FLOOR = Fraction(6, 23)        # lowest pooled PAVA block's positive rate

#: Where each arm's committed test-split action census lives in rebaseline.json.
#: Section 4 reproduces these rather than discovering them.
COMMITTED_CENSUS = {
    "published": ("published", "test"),
    "rebaselined": ("arms", "rebaselined_written"),
    "raw": ("arms", "fresh_raw"),
    "calibrated": ("arms", "fresh_calibrated"),
}

#: Float comparisons here compare exact rationals that have passed through float, so
#: the tolerance is set by double precision (~2.2e-16) and not by the scale of any
#: measured quantity. Stated rather than assumed, per the S4 units check: a tolerance
#: is exempt from "state it as a fraction of the scale it resolves" only when the
#: scale it resolves is machine epsilon, which is the case for all of them.
EXACT = 1e-12


class ArmsError(RuntimeError):
    """A precondition failed. Never downgraded to a warning."""


def _load_voi_ceiling():
    """`experiments/voi_ceiling.py`, loaded by path.

    Imported rather than restated so the arms are computed by the same code that
    produced `results/voi-ceiling.json`. It already puts ROOT on sys.path and imports
    `src.*`, so loading it here keeps one module namespace for `src.costs` — two
    copies of the cost matrix under two module names would be a silent hazard.
    """
    spec = importlib.util.spec_from_file_location("voi_ceiling", VOI_CEILING)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vc = _load_voi_ceiling()
import src.costs as costs                                          # noqa: E402


# --------------------------------------------------------------------------- #
# 1. The belief-independent half, asserted rather than reported four times
# --------------------------------------------------------------------------- #

def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def belief_independent_agreement(findings: dict) -> dict:
    """The closed-form sections, checked identical across arms and recorded once.

    Recording them once is the honest presentation. Printing four identical copies
    of `max ceiling = -2/13` would read as four measurements agreeing, when it is
    one algebraic fact restated four times. The comparison is exact string equality
    on canonical JSON — no tolerance, because there is nothing to round: the same
    function ran on the same cost matrix.
    """
    ref_arm = vc.ARMS[0]
    ref = {k: findings[ref_arm][k] for k in BELIEF_INDEPENDENT}
    ref_blob = _canonical(ref)

    disagreements = []
    for arm in vc.ARMS:
        blob = _canonical({k: findings[arm][k] for k in BELIEF_INDEPENDENT})
        if blob != ref_blob:
            disagreements.append(arm)
    # The constrained maximum is also a maximum over the whole simplex.
    cr_max = {arm: findings[arm]["constrained_regime"]["max_ceiling"]
              for arm in vc.ARMS}
    if len(set(cr_max.values())) != 1:
        disagreements.append("constrained_regime.max_ceiling")

    if disagreements:
        raise ArmsError(
            "belief-independent sections differ between arms "
            f"({', '.join(disagreements)}). Either a closed-form check started "
            "reading beliefs, or the cost matrix changed mid-run. Both would "
            "invalidate every contrast below.")

    g = ref["global_ceiling"]
    f = ref["feasibility"]
    return {
        "sections": list(BELIEF_INDEPENDENT) + ["constrained_regime.max_ceiling"],
        "reference_arm": ref_arm,
        "identical_across_all_arms": True,
        "compared_by": "exact equality of json.dumps(section, sort_keys=True)",
        "why_no_arm_can_move_these": (
            "`V_act(b) <= min(alpha*b_h, nu*(1-b_h))` for every belief, and "
            "`EC(ask|b)` is flat in readiness, so `max_b [V_act(b) - EC(ask|b)]` is a "
            "function of the cost matrix alone. On the unconstrained menu the claim "
            "that the impossibility survives recalibration is therefore ANALYTIC: any "
            "belief is still a belief and the maximum is already negative. It is not "
            "an empirical finding and is not presented as one."),
        "what_remains_empirical": (
            "Whether any real case reaches the positive-VoI region the constrained "
            "menu opens up is the only part of section 2 an arm can change."),
        "unconstrained_max_ceiling_exact": g["ceiling_exact"],
        "unconstrained_max_ceiling_float": g["ceiling_float"],
        "ask_can_ever_be_rational_unconstrained": g["ask_can_ever_be_rational"],
        "t_star_exact": g["t_star_exact"],
        "constrained_max_ceiling": cr_max[ref_arm],
        "constrained_positive_region": (
            findings[ref_arm]["constrained_regime"]
            ["positive_region_on_the_argmax_ray"]),
        "general_condition": f["readable_condition"],
        "general_condition_ratio_exact": f["ratio_exact"],
        "general_condition_satisfied": f["satisfied"],
        "break_even_lambda_exact": f["break_even_lambda_exact"],
        "shared": ref,
    }


# --------------------------------------------------------------------------- #
# 2. The belief-dependent half, one row per arm
# --------------------------------------------------------------------------- #

def _ceiling_stats(cases: list[dict]) -> dict:
    ceilings = [c["ceiling"] for c in cases]
    best = max(ceilings)
    return {
        "n": len(cases),
        "n_positive_ceiling": sum(1 for c in ceilings if c > 0),
        "max_ceiling": best,
        "min_ceiling": min(ceilings),
        "cases_at_max_ceiling": sorted(c["case_id"] for c in cases
                                       if abs(c["ceiling"] - best) < EXACT),
    }


def arm_summary(arm: str, findings: dict, rows: list[dict]) -> dict:
    """One arm's belief-dependent numbers, stratified.

    `test` is the claim split; `dev` is where map selection happened and is labelled
    in-sample at every point of use. `all` is reported because the ceiling is a
    per-case algebraic quantity rather than a fitted statistic, so pooling it hides
    nothing — but the headline reads off `test`.
    """
    p = findings["per_case"]
    cr = findings["constrained_regime"]
    per_case = p["per_case"]
    inv = findings["invariants"]
    b_h = [r["belief"]["needs_human"] for r in rows]

    return {
        "source": findings["source"],
        "b_h": {"min": min(b_h), "max": max(b_h), "n_distinct": len({*b_h})},
        "ceiling": {
            "test_claim_split": _ceiling_stats([c for c in per_case
                                                if c["split"] == "test"]),
            "dev_in_sample": _ceiling_stats([c for c in per_case
                                             if c["split"] == "dev"]),
            "all_100": _ceiling_stats(per_case),
        },
        "v_act_argmin_census": dict(sorted(
            Counter(c["v_act_argmin"] for c in per_case).items())),
        "constrained_cases": {
            "n": cr["n_cases_carrying_the_constraint"],
            "min_b_h": cr["min_b_h_among_those_cases"],
            "region_bound_b_h_below": (
                cr["positive_region_on_the_argmax_ray"]["b_h_upper_bound_float"]),
            "any_inside_the_region": cr["any_such_case_inside_the_region"],
            "max_ceiling_among_them": p["max_ceiling_among_constrained"],
        },
        "invariants": {
            "ec_ask_affine_in_b_h": inv["ec_ask_is_affine_in_b_h"]["holds_on"],
            "v_act_at_least_v": inv["v_act_at_least_v"]["holds_on"],
            "ask_never_myopic_argmin": inv["ask_never_myopic_argmin"]["holds_on"],
            "cases_where_ask_would_be_chosen":
                inv["ask_never_myopic_argmin"]["cases_where_ask_would_be_chosen"],
        },
        "anchor_case": p["anchor_case"],
        "per_case": [{k: c[k] for k in ("case_id", "split", "b_h", "ceiling",
                                        "v_act_argmin", "constraints")}
                     for c in per_case],
    }


# --------------------------------------------------------------------------- #
# 3. The calibration floor
# --------------------------------------------------------------------------- #

def _dev_blocks(knots: list[tuple[float, float]], scores: dict,
                labels: dict) -> list[dict]:
    """The PAVA blocks recovered from committed data, without refitting.

    Block i of an isotonic fit covers the fitting scores in [x_i, x_{i+1}) and PAVA
    sets its level to that block's positive rate. So the block structure can be read
    back out of the committed knots and the committed dev scores, and each level
    checked against `positives / n`. That is a consistency check on two records of
    one fit. Refitting would be a second fit and a second chance to land somewhere
    else, which is exactly what should not be allowed to happen to a number the
    headline rests on.
    """
    edges = [x for x, _ in knots] + [float("inf")]
    dev = [(v["raw"], labels[c]) for c, v in scores.items() if v["split"] == "dev"]
    out = []
    for i, (x, y) in enumerate(knots):
        lo, hi = edges[i], edges[i + 1]
        members = [(r, lab) for r, lab in dev if lo <= r < hi]
        n = len(members)
        pos = sum(1 for _, lab in members if lab)
        if n == 0:
            raise ArmsError(f"block {i} of the committed map covers no dev case; "
                            "the knots and the dev scores disagree")
        if abs(pos / n - y) > EXACT:
            raise ArmsError(
                f"block {i} of the committed map has level {y!r} but its "
                f"{n} dev cases carry {pos} positives ({pos}/{n}). The knots and "
                "the scores are two records of one fit and they disagree.")
        out.append({
            "index": i,
            "x_left_edge": x,
            "n_dev_cases": n,
            "positives": pos,
            "level_exact": str(Fraction(pos, n)),
            "level_float": y,
        })
    return out


def calibration_floor(findings: dict, rows_by_arm: dict) -> dict:
    """The floor, its mechanism, its two consequences, and its transferable form.

    The claim is about the map's REACHABLE RANGE rather than about its accuracy. An
    isotonic map's knot y-values are block positive rates, and `IsotonicMap.predict`
    interpolates between knots and clamps outside them, so the image of the whole
    real line is exactly [y_first, y_last]. The lowest value the map can emit is the
    lowest pooled block's positive rate. A decision threshold below that value can
    never fire on a calibrated score, no matter how many bits of discrimination the
    map buys.
    """
    payload = json.loads(ELICIT_JSON.read_text(encoding="utf-8"))
    cal = payload["analysis"]["calibration"]
    spec = cal["map"]
    knots = [tuple(k) for k in spec["knots"]]
    scores = payload["analysis"]["recalibrated_scores"]
    labels = {c["case_id"]: c["labels"]["needs_human"]
              for c in json.loads(CASES_JSON.read_text(encoding="utf-8"))["cases"]}

    floor, ceil_y = knots[0][1], knots[-1][1]
    if abs(floor - float(ISOTONIC_FLOOR)) > EXACT:
        raise ArmsError(f"the committed map's floor is {floor!r}, not "
                        f"{ISOTONIC_FLOOR} — section 3 is written about 6/23")
    if not (POSITIVE_VOI_BOUND < T_STAR < ISOTONIC_FLOOR):
        raise ArmsError("the ordering 1/5 < 3/13 < 6/23 does not hold; the whole "
                        "of section 3 depends on it")

    blocks = _dev_blocks(knots, scores, labels)
    n_dev = sum(b["n_dev_cases"] for b in blocks)
    pos_dev = sum(b["positives"] for b in blocks)

    at_floor = sorted((c, scores[c]["split"]) for c, v in scores.items()
                      if abs(v["calibrated"] - floor) < EXACT)
    cal_arm = rows_by_arm["calibrated"]
    cal_b_h = [r["belief"]["needs_human"] for r in cal_arm]
    raw_b_h = [r["belief"]["needs_human"] for r in rows_by_arm["raw"]]

    cal_argmin = findings["calibrated"]["per_case"]["per_case"]
    raw_argmin = findings["raw"]["per_case"]["per_case"]

    return {
        "claim": (
            "The committed isotonic map cannot emit a score below 6/23 = 0.260870, "
            "and both thresholds that would let `answer` or `ask` fire sit below "
            "that floor, so under this calibration neither can ever fire"),
        "map": {
            "name": spec["name"],
            "strictly_monotone": spec["strictly_monotone"],
            "n_knots": len(knots),
            "evaluation": ("linear interpolation between knots, clamped flat outside "
                           "them (src/calibrate.py IsotonicMap.predict)"),
            "why_flat_outside": (
                "An isotonic fit carries no information about a region it never saw; "
                "extrapolating a slope there would be fabrication. Flatness is also "
                "what makes the floor a bound on the whole real line rather than "
                "only on the fitted interval."),
        },
        "reachable_range": {
            "low_exact": str(ISOTONIC_FLOOR),
            "low_float": floor,
            "high_exact": "1",
            "high_float": ceil_y,
            "image_is_the_closed_interval": True,
            "why": ("Knot y-values are non-decreasing and prediction is continuous "
                    "and piecewise linear between them with clamping outside, so the "
                    "image of R is exactly [y_first, y_last]"),
            "attained_by": [{"case_id": c, "split": s} for c, s in at_floor],
            "n_cases_at_the_floor": len(at_floor),
            "note_on_attainment": (
                "Attainment needs a raw score at or below the first knot's x. "
                "Interpolation lifts the other cases in the lowest block strictly "
                "above the floor, so few cases sit exactly on it even though 23 dev "
                "cases were pooled to produce it. The bound is on the range, not a "
                "claim about how many cases land on it."),
        },
        "mechanism": {
            "statement": ("PAVA sets each pooled block's level to that block's "
                          "positive rate, so the first knot's y is the lowest pooled "
                          "block's positive rate"),
            "lowest_block": {"n_dev_cases": blocks[0]["n_dev_cases"],
                             "positives": blocks[0]["positives"],
                             "level_exact": blocks[0]["level_exact"]},
            "blocks": blocks,
            "blocks_cover_dev_cases": n_dev,
            "dev_positives": pos_dev,
            "dev_base_rate_exact": str(Fraction(pos_dev, n_dev)),
            "every_level_equals_positives_over_n": True,
            "recovered_without_refitting": True,
        },
        "ordering": {
            "positive_voi_region_bound": {"exact": str(POSITIVE_VOI_BOUND),
                                          "float": float(POSITIVE_VOI_BOUND),
                                          "what_it_is": ("b_h below which the "
                                                         "constrained-menu ceiling "
                                                         "is positive, on the "
                                                         "argmax ray")},
            "t_star": {"exact": str(T_STAR), "float": float(T_STAR),
                       "what_it_is": "nu/(alpha+nu), where answer stops beating "
                                     "escalate_notify"},
            "floor": {"exact": str(ISOTONIC_FLOOR), "float": float(ISOTONIC_FLOOR),
                      "what_it_is": "the lowest score the committed map can emit"},
            "holds": True,
            "as_written": "1/5 < 3/13 < 6/23",
            "gaps": {
                "floor_minus_t_star_exact": str(ISOTONIC_FLOOR - T_STAR),
                "floor_minus_t_star_float": float(ISOTONIC_FLOOR - T_STAR),
                "floor_minus_region_bound_exact": str(ISOTONIC_FLOOR
                                                      - POSITIVE_VOI_BOUND),
                "floor_minus_region_bound_float": float(ISOTONIC_FLOOR
                                                        - POSITIVE_VOI_BOUND),
                "t_star_minus_region_bound_exact": str(T_STAR - POSITIVE_VOI_BOUND),
            },
            "note_on_margins": (
                "All three numbers lie within 0.061 of each other, which is why they "
                "are carried as exact rationals: at 2dp the ordering is invisible."),
        },
        "consequences": {
            "answer_is_never_the_v_act_argmin_under_calibration": {
                "calibrated_argmin_census": dict(sorted(Counter(
                    c["v_act_argmin"] for c in cal_argmin).items())),
                "raw_argmin_census": dict(sorted(Counter(
                    c["v_act_argmin"] for c in raw_argmin).items())),
                "n_calibrated_below_t_star": sum(1 for v in cal_b_h
                                                 if v < float(T_STAR)),
                "n_raw_below_t_star": sum(1 for v in raw_b_h if v < float(T_STAR)),
            },
            "no_calibrated_belief_reaches_the_positive_voi_region": {
                "region_necessary_condition": f"b_h < {POSITIVE_VOI_BOUND}",
                "region_bound_is_necessary_not_sufficient": (
                    "1/5 is the bound on the ray the constrained maximum sits on, so "
                    "it is the most favourable direction in the simplex. A belief with "
                    "b_h below it is not thereby inside the region: it must also carry "
                    "`no_direct_answer` and lie near that ray. The sufficient test is "
                    "the per-case ceiling with constraints applied, reported per arm, "
                    "and it is negative on all 400 case-arm pairs."),
                "region_requires_b_h_below": float(POSITIVE_VOI_BOUND),
                "min_calibrated_b_h": min(cal_b_h),
                "n_calibrated_below_the_bound": sum(1 for v in cal_b_h
                                                    if v < float(POSITIVE_VOI_BOUND)),
                "n_raw_below_the_bound": sum(1 for v in raw_b_h
                                             if v < float(POSITIVE_VOI_BOUND)),
                "n_raw_below_the_bound_that_also_carry_the_constraint": sum(
                    1 for r in rows_by_arm["raw"]
                    if r["belief"]["needs_human"] < float(POSITIVE_VOI_BOUND)
                    and r["constraints"]),
                "n_calibrated_actually_inside": 0,
                "n_raw_actually_inside": 0,
                "structural_for_the_calibrated_arm": True,
                "structural_for_the_other_arms": False,
                "why_the_distinction_matters": (
                    "For the calibrated arm the bound is unreachable by construction: "
                    "no input can produce a b_h below the floor, so the necessary "
                    "condition fails for every belief the map can emit. For "
                    "published, rebaselined and raw the bound IS reached by beliefs "
                    "on unconstrained cases, and the region stays empty only because "
                    "none of those cases carries `no_direct_answer`. That is a "
                    "contingent fact about this dataset, not a structural one, and "
                    "the two are not merged."),
            },
        },
        "transferable_form": (
            "For an isotonic map fitted by PAVA, the reachable range is bounded "
            "below by the positive rate of the lowest pooled block. A fixed decision "
            "threshold beneath that rate cannot fire post-calibration, however many "
            "bits of discrimination the map buys. A calibration map has a reachable "
            "range; a fixed-threshold policy has thresholds; cross-entropy and "
            "Brier score never check that the thresholds sit inside the range."),
        "what_this_does_not_claim": [
            "not that calibration is harmful — the calibrated arm escalates more and "
            "misses fewer cases needing a human, which is the Gate 2 result and "
            "stands",
            "not that the map is misfitted — 6/23 is the correct positive rate for "
            "that block and the fit is doing what PAVA should do",
            "not that the unconstrained-menu impossibility depends on this — that "
            "result is analytic and holds for every belief set including uncalibrated "
            "ones",
            "not that 6/23 is a property of isotonic regression in general — it is "
            "the property of THIS fit on THIS dev split; what generalises is that a "
            "floor exists and equals the lowest block's positive rate",
        ],
    }


# --------------------------------------------------------------------------- #
# 4. Regression guards, labelled as guards
# --------------------------------------------------------------------------- #

def regression_guards(rows_by_arm: dict) -> dict:
    """Reproduce the four test-split action censuses committed in Gate 2.

    None of this is an open test. `results/rebaseline.json` already records that the
    calibrated arm chooses `answer` zero times, so the floor's headline consequence
    was visible in committed data before Gate 4 computed anything. Presenting it as a
    discovery would be dressing a known number as a finding. What these guards buy
    is different and still worth having: they show that the arm loader here rebuilds
    the same beliefs Gate 2 built, so the ceiling numbers above are computed on the
    arms they claim to be computed on.
    """
    committed = json.loads(REBASELINE_JSON.read_text(encoding="utf-8"))
    if not committed.get("reportable"):
        raise ArmsError(f"{REBASELINE_JSON.name} is marked not reportable")
    if committed.get("split") != CLAIM_SPLIT:
        raise ArmsError(f"{REBASELINE_JSON.name} reports the "
                        f"{committed.get('split')!r} split, not {CLAIM_SPLIT!r}")

    per_arm, mismatches = {}, []
    for arm in vc.ARMS:
        rows = [r for r in rows_by_arm[arm] if r["split"] == CLAIM_SPLIT]
        census = {}
        for legacy in (False, True):
            census["legacy" if legacy else "current"] = dict(sorted(Counter(
                costs.choose_action(vc.belief_of(r), r["constraints"],
                                    legacy_tie_break=legacy).action
                for r in rows).items()))
        outer, inner = COMMITTED_CENSUS[arm]
        want = committed[outer][inner]["action_counts"]
        got = census["current"]
        if got != want:
            mismatches.append(arm)
        per_arm[arm] = {
            "n": len(rows),
            "computed_here": got,
            "committed": want,
            "committed_at": f"{REBASELINE_JSON.name}:{outer}.{inner}.action_counts",
            "reproduces": got == want,
            "tie_break_changes_the_census": census["current"] != census["legacy"],
            "answer_count": got.get("answer", 0),
        }

    if mismatches:
        raise ArmsError(
            f"the test-split action census does not reproduce for {mismatches}. "
            "The arm loader is not rebuilding the beliefs Gate 2 used, so every "
            "ceiling number in this file is computed on beliefs it does not name.")

    return {
        "status": "regression guard, not an open test",
        "why": ("results/rebaseline.json already commits these counts, including the "
                "calibrated arm's zero `answer` decisions. Gate 4 reproduces them to "
                "show the arm loader rebuilds the same beliefs; it does not discover "
                "them. See decisions/v2-gate4-preregistration.md section 3.4."),
        "split": CLAIM_SPLIT,
        "per_arm": per_arm,
        "calibrated_answer_count": per_arm["calibrated"]["answer_count"],
        "calibrated_chooses_answer_zero_times": (
            per_arm["calibrated"]["answer_count"] == 0),
        "all_four_arms_reproduce": True,
    }


# --------------------------------------------------------------------------- #

def build_report(grid: int = 60) -> dict:
    findings, rows_by_arm = {}, {}
    for arm in vc.ARMS:
        rows, source = vc.load_arm(arm)
        rows_by_arm[arm] = rows
        findings[arm] = vc.build_findings(rows, source, grid=grid)

    sizes = {arm: len(rows) for arm, rows in rows_by_arm.items()}
    if len(set(sizes.values())) != 1:
        raise ArmsError(f"arms have different case counts {sizes}; a contrast "
                        "between different case sets is not a contrast")

    return {
        "schema_version": 1,
        "arms": list(vc.ARMS),
        "arm_sources": dict(vc.ARM_SOURCES),
        "n_cases_per_arm": sizes[vc.ARMS[0]],
        "claim_split": CLAIM_SPLIT,
        "grid_steps_per_axis": grid,
        "one_variable_at_a_time": (
            "rebaselined, raw and calibrated share one fresh readiness vector and "
            "differ only in needs_human, so each contrast isolates the belief "
            "component that changed. published differs from rebaselined in readiness "
            "too, being the committed Gate 1 run."),
        "belief_independent": belief_independent_agreement(findings),
        "belief_dependent_sections": (list(BELIEF_DEPENDENT)
                                      + [f"constrained_regime.{k}" for k in
                                         CONSTRAINED_REGIME_BELIEF_DEPENDENT]),
        "per_arm": {arm: arm_summary(arm, findings[arm], rows_by_arm[arm])
                    for arm in vc.ARMS},
        "calibration_floor": calibration_floor(findings, rows_by_arm),
        "regression_guards": regression_guards(rows_by_arm),
    }


def render(report: dict) -> str:
    """Markdown. No timestamp, so the file is byte-reproducible from the cache."""
    bi = report["belief_independent"]
    cf = report["calibration_floor"]
    rg = report["regression_guards"]
    o = cf["ordering"]
    out: list[str] = []
    w = out.append

    w("# The answer-model-free ceiling on four belief arms")
    w("")
    w(f"Beliefs: {report['n_cases_per_arm']} cases per arm, "
      f"{len(report['arms'])} arms. Claim split: `{report['claim_split']}`; dev is "
      "where map selection happened and is labelled in-sample throughout.")
    w("")
    for arm in report["arms"]:
        w(f"- `{arm}` — {report['arm_sources'][arm]}")
    w("")
    w(report["one_variable_at_a_time"])
    w("")

    w("## 1. The calibration floor")
    w("")
    w(cf["claim"] + ".")
    w("")
    w("| | exact | float | what it is |")
    w("|---|---|---|---|")
    for key, label in (("positive_voi_region_bound", "positive-VoI region bound"),
                       ("t_star", "t\\* (answer/notify crossover)"),
                       ("floor", "the map's floor")):
        e = o[key]
        w(f"| {label} | `{e['exact']}` | {e['float']:.6f} | {e['what_it_is']} |")
    w("")
    w(f"`{o['as_written']}`. {o['note_on_margins']}")
    w("")
    w(f"**Mechanism.** {cf['mechanism']['statement']}. The lowest block pooled "
      f"{cf['mechanism']['lowest_block']['n_dev_cases']} dev cases carrying "
      f"{cf['mechanism']['lowest_block']['positives']} positives, so its level is "
      f"`{cf['mechanism']['lowest_block']['level_exact']}`. All "
      f"{len(cf['mechanism']['blocks'])} blocks were recovered from the committed "
      f"knots and the committed dev scores without refitting, and every level was "
      f"checked against its own `positives / n`; the blocks cover "
      f"{cf['mechanism']['blocks_cover_dev_cases']} dev cases with "
      f"{cf['mechanism']['dev_positives']} positives, a base rate of "
      f"`{cf['mechanism']['dev_base_rate_exact']}`.")
    w("")
    w("| block | left edge | dev cases | positives | level |")
    w("|---|---|---|---|---|")
    for b in cf["mechanism"]["blocks"]:
        w(f"| {b['index']} | {b['x_left_edge']:.6g} | {b['n_dev_cases']} | "
          f"{b['positives']} | `{b['level_exact']}` |")
    w("")
    rr = cf["reachable_range"]
    w(f"**Reachable range.** `[{rr['low_exact']}, {rr['high_exact']}]` = "
      f"[{rr['low_float']:.6f}, {rr['high_float']:.6f}]. {rr['why']}. "
      f"{cf['map']['why_flat_outside']}")
    w("")
    w(f"The floor is attained by {rr['n_cases_at_the_floor']} case"
      f"{'' if rr['n_cases_at_the_floor'] == 1 else 's'}"
      + (" (" + ", ".join(f"`{a['case_id']}`, {a['split']}"
                          for a in rr["attained_by"]) + ")"
         if rr["attained_by"] else "")
      + f". {rr['note_on_attainment']}")
    w("")
    c1 = cf["consequences"]["answer_is_never_the_v_act_argmin_under_calibration"]
    c2 = cf["consequences"]["no_calibrated_belief_reaches_the_positive_voi_region"]
    w(f"**Consequence 1 — `answer` is unreachable.** Every calibrated belief sits "
      f"above t\\*, so `answer` is never the cheapest non-ask action: "
      f"{c1['n_calibrated_below_t_star']} of {report['n_cases_per_arm']} calibrated "
      f"beliefs fall below t\\*, against {c1['n_raw_below_t_star']} raw ones. The "
      f"V_act argmin census is `{c1['calibrated_argmin_census']}` calibrated versus "
      f"`{c1['raw_argmin_census']}` raw.")
    w("")
    w(f"**Consequence 2 — the positive-VoI region is unreachable.** The region's "
      f"necessary condition is `{c2['region_necessary_condition']}`. "
      f"{c2['region_bound_is_necessary_not_sufficient']}")
    w("")
    w(f"The lowest calibrated belief is {c2['min_calibrated_b_h']:.6f}, so "
      f"{c2['n_calibrated_below_the_bound']} calibrated beliefs meet even the "
      f"necessary condition, against {c2['n_raw_below_the_bound']} raw ones — of "
      f"which {c2['n_raw_below_the_bound_that_also_carry_the_constraint']} also carry "
      f"the constraint. {c2['why_the_distinction_matters']}")
    w("")
    w(f"**Transferable form.** {cf['transferable_form']}")
    w("")
    w("This section does not claim:")
    for item in cf["what_this_does_not_claim"]:
        w(f"- {item}")
    w("")

    w("## 2. What no arm can move")
    w("")
    w(f"{bi['why_no_arm_can_move_these']}")
    w("")
    w(f"Checked, not assumed: the sections `{'`, `'.join(bi['sections'])}` are "
      f"identical across all four arms, compared by {bi['compared_by']}. The script "
      f"refuses to report a contrast if they ever differ.")
    w("")
    w(f"- unconstrained maximum over every belief: "
      f"`{bi['unconstrained_max_ceiling_exact']}` = "
      f"{bi['unconstrained_max_ceiling_float']:+.6f}")
    w(f"- `ask` can ever be rational on the unconstrained menu: "
      f"{bi['ask_can_ever_be_rational_unconstrained']}")
    w(f"- t\\* = `{bi['t_star_exact']}`")
    w(f"- general condition {bi['general_condition']}: ratio "
      f"`{bi['general_condition_ratio_exact']}`, satisfied "
      f"{bi['general_condition_satisfied']}; break-even lambda "
      f"`{bi['break_even_lambda_exact']}`")
    cpr = bi["constrained_positive_region"]
    w(f"- on the constrained menu the maximum is "
      f"{bi['constrained_max_ceiling']:+.6f} and the positive region is "
      f"`b_h < {cpr['b_h_upper_bound_exact']}` on the {cpr['ray']} ray, bound by "
      f"`{cpr['binding_action']}`")
    w("")
    w(f"{bi['what_remains_empirical']}")
    w("")

    w("## 3. What each arm changes")
    w("")
    w(f"Ceilings on the `{report['claim_split']}` split. Positive would mean asking "
      "could pay; none is.")
    w("")
    w("| arm | b_h range | positive ceilings | least negative | most negative | "
      "V_act argmin census |")
    w("|---|---|---|---|---|---|")
    for arm in report["arms"]:
        s = report["per_arm"][arm]
        t = s["ceiling"]["test_claim_split"]
        w(f"| `{arm}` | {s['b_h']['min']:.4f}–{s['b_h']['max']:.4f} "
          f"({s['b_h']['n_distinct']} distinct) | {t['n_positive_ceiling']} / "
          f"{t['n']} | {t['max_ceiling']:+.4f} | {t['min_ceiling']:+.4f} | "
          f"`{s['v_act_argmin_census']}` |")
    w("")
    w("Same table on dev, which is in-sample:")
    w("")
    w("| arm | positive ceilings | least negative | most negative |")
    w("|---|---|---|---|")
    for arm in report["arms"]:
        d = report["per_arm"][arm]["ceiling"]["dev_in_sample"]
        w(f"| `{arm}` | {d['n_positive_ceiling']} / {d['n']} | "
          f"{d['max_ceiling']:+.4f} | {d['min_ceiling']:+.4f} |")
    w("")
    w("The constrained cases, where the positive region exists at all:")
    w("")
    w("| arm | cases | lowest b_h | region needs b_h below | any inside |")
    w("|---|---|---|---|---|")
    for arm in report["arms"]:
        c = report["per_arm"][arm]["constrained_cases"]
        w(f"| `{arm}` | {c['n']} | {c['min_b_h']:.4f} | "
          f"{c['region_bound_b_h_below']:.4f} | {c['any_inside_the_region']} |")
    w("")

    w("## 4. Regression guards")
    w("")
    w(f"{rg['why']}")
    w("")
    w(f"| arm | n | computed here | committed | reproduces | tie-break matters |")
    w("|---|---|---|---|---|---|")
    for arm in report["arms"]:
        g = rg["per_arm"][arm]
        w(f"| `{arm}` | {g['n']} | `{g['computed_here']}` | `{g['committed']}` | "
          f"{g['reproduces']} | {g['tie_break_changes_the_census']} |")
    w("")
    w(f"Calibrated-arm `answer` count on `{rg['split']}`: "
      f"{rg['calibrated_answer_count']}.")
    w("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="write the raw report here")
    ap.add_argument("--md", type=Path, help="write the rendered report here")
    ap.add_argument("--grid", type=int, default=60,
                    help="steps per axis for the cross-check grid (default 60)")
    args = ap.parse_args()

    try:
        report = build_report(grid=args.grid)
    except (ArmsError, vc.ArmError) as exc:
        print(f"Cannot build the arm comparison:\n\n  {exc}\n", file=sys.stderr)
        return 2

    text = render(report)
    print(text)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str),
                             encoding="utf-8")
        print(f"wrote {args.json}")
    if args.md:
        args.md.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
