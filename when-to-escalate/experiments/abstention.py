#!/usr/bin/env python3
"""
The cost of abstention, on three belief arms, under all three OQ2 variants.

OQ2 (`decisions/v2-definitions.md` section 7) left three ways to turn "the agent is
uncertain" into an action and deferred the choice to this gate so the cost would be
measured rather than predicted. All three are built here:

    (c) diagnostic          myopic argmin, policy unchanged; abstention is reported
    (b) fallback ordering   where the fallback was `escalate_notify`, use
                            `escalate_pause` instead
    (a) threshold override  `H(b) >= tau` forces `escalate_pause`, overriding the
                            matrix

Abstention resolves to `escalate_pause` — the agent stops and hands over — not to
`escalate_notify` (decisions/v2-gate4-preregistration.md section 5).

The answer splits the same way the ceiling did. One half is a property of
`src.costs.COST` and no belief set or threshold can move it: `escalate_pause` costs
strictly more than `escalate_notify` in all six labelled states, so any rule that
resolves a notify toward a pause raises realised cost by construction, and both
count as escalations so no such rule can change the miss count. Section 1 records
that once, as arithmetic on the matrix, and does not restate it per arm.

What is empirical is the size: how much cost, on how many cases, against how many
misses avoided. That is sections 3 to 6, on the `test` split, with the `dev` half
shown and labelled in-sample.

`tau` is the one new tunable at this gate, and it is defined as the deciles of the
observed `H(b)` distribution on the arm being scored, not as absolute bits — the
observed distribution is bunched into a 0.83-bit band, so an absolute grid would
spend most of its points where no cases are. Both readings are reported: the
quantile and the bits it lands on. Quantile grids are not comparable across arms in
absolute bits, because `H(b)` moves when `b_h` moves; reporting both is the
mitigation and it is stated rather than left to be noticed.

This script measures. It does not choose between (a), (b) and (c) — that call is
made at the Gate 4 close, on these numbers.

Reads only committed artifacts. Never calls a provider.

    python experiments/abstention.py
    python experiments/abstention.py --json results/abstention.json \
                                     --md results/abstention.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VOI_CEILING = ROOT / "experiments" / "voi_ceiling.py"
ANSWER_MODEL = ROOT / "experiments" / "answer_model.py"
REBASELINE_JSON = ROOT / "results" / "rebaseline.json"

#: Three arms, not four. `rebaselined` would add a column about cache drift, and
#: abstention has nothing to do with cache drift
#: (decisions/v2-gate4-preregistration.md section 5.1).
ARMS = ("published", "raw", "calibrated")

#: The claim split. Map selection happened on dev, so dev is in-sample and is
#: labelled that way everywhere it appears. All 100 cases are computed either way.
CLAIM_SPLIT = "test"

#: run.json used the legacy tie-break; the fresh arms do not. Both are computed and
#: the difference is reported rather than assumed away.
FRESH_LEGACY_TIE_BREAK = False

#: The pre-registered grid: deciles, 0% to 100%. Eleven points, so the extremes are
#: included — tau at the 0th decile fires on every case and tau at the 100th fires
#: only on the argmax, which brackets the range a threshold could take.
QUANTILES = tuple(i / 10 for i in range(11))

#: The population the deciles are taken over. All 100 cases of the arm being scored,
#: which is what reproduces section 6.1's pre-registered table for `published`.
#: Quantiles of H(b) use no labels, so this is not label leakage; it is a choice of
#: population and is recorded as one.
GRID_POPULATION = "all_100_cases_of_the_arm_being_scored"

#: Where each arm's committed test-split score lives in rebaseline.json. The
#: baseline is checked against the committed artifact, not trusted because it shares
#: code with it.
COMMITTED_BASELINE = {
    "published": ("published", "test"),
    "raw": ("arms", "fresh_raw"),
    "calibrated": ("arms", "fresh_calibrated"),
}

#: Float comparisons here compare integers and exact rationals that have passed
#: through float. The scale being resolved is double precision, not the scale of any
#: measured quantity, which is why this one is absolute (S4).
EXACT = 1e-9

#: `H(b)` is quantised to this many decimals before any threshold comparison.
#:
#: Not cosmetic. Cases with the same belief can produce `H(b)` values differing in
#: the last bit, because `joint_entropy` sums six terms whose order depends on how
#: the belief was built. On the published arm five such pairs exist, the largest
#: differing by 8.9e-16. Left unquantised they make the sorted sample carry 24
#: apparently distinct values where 19 exist, and the decile grid then reads two
#: mathematically identical thresholds as different ones: the 10th and 20th
#: percentile are both 1.62577524303632, yet fired on 49 and 44 test cases because
#: the second sat 2 ulp higher.
#:
#: The S4 justification is a measured ratio, not a preference. The rule must absorb
#: gaps of at most 8.9e-16 and must not cross the smallest genuine gap between
#: distinct `H(b)` values, which is 4.97e-06 on the closest arm. 1e-12 sits about
#: three orders above the noise and six below the signal. Both scales are recomputed
#: per arm and reported in `float_noise`, so the margin is checked at run time rather
#: than trusted from this comment.
H_DECIMALS = 12


class AbstentionError(RuntimeError):
    """A precondition failed. Never downgraded to a warning."""


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: `voi_ceiling` first: it puts ROOT on sys.path and imports `src.*`, so everything
#: below shares one `src.costs` and therefore one cost matrix.
vc = _load("voi_ceiling", VOI_CEILING)
am = _load("answer_model", ANSWER_MODEL)

import src.costs as costs                                          # noqa: E402
from src.belief import Belief                                      # noqa: E402
from src.questions import STATES, widen                            # noqa: E402


# --------------------------------------------------------------------------- #
# v1's scoring definitions, imported in behaviour and restated in one line each
# --------------------------------------------------------------------------- #

def realised_cost(action: str, labels: dict) -> float:
    """Score one action against the true state, as run_policies.realised_cost does."""
    return costs.COST[action][(labels["readiness"], labels["needs_human"])]


def is_escalation(action: str) -> bool:
    """v1 counts either escalate action as an escalation (run_policies.summarise)."""
    return action.startswith("escalate")


def score(decisions: list[dict]) -> dict:
    """Aggregate exactly as run_policies.summarise and rebaseline.score_arm do."""
    n = len(decisions)
    if not n:
        raise AbstentionError("cannot score an empty decision set")
    total = sum(d["realised_cost"] for d in decisions)
    tp = sum(1 for d in decisions if is_escalation(d["action"]) and d["needs_human"])
    fp = sum(1 for d in decisions
             if is_escalation(d["action"]) and not d["needs_human"])
    fn = sum(1 for d in decisions
             if not is_escalation(d["action"]) and d["needs_human"])
    return {
        "n": n,
        "total_cost": round(total, 2),
        "mean_cost": round(total / n, 4),
        "missed_escalations": fn,
        "escalation_precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "escalation_recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
        "action_counts": dict(sorted(Counter(d["action"] for d in decisions).items())),
    }


# --------------------------------------------------------------------------- #
# 1. What the cost matrix settles before any belief is read
# --------------------------------------------------------------------------- #

def matrix_facts() -> dict:
    """`escalate_pause` against `escalate_notify`, state by state, in exact integers.

    Both variants that act on abstention resolve toward `escalate_pause`. Whether
    that can ever be cheaper than the notify it replaces is a question about six
    numbers in `src.costs.COST`, so it is answered here rather than inferred from a
    cost total later. If pause were cheaper anywhere, the aggregate deltas in
    sections 4 and 5 would need a per-state breakdown to be readable; it is not.
    """
    states = [(r, h) for h in (False, True)
              for r in ("hot", "warm", "cold")]
    rows = []
    for state in states:
        pause = Fraction(costs.COST["escalate_pause"][state]).limit_denominator()
        notify = Fraction(costs.COST["escalate_notify"][state]).limit_denominator()
        answer = Fraction(costs.COST["answer"][state]).limit_denominator()
        rows.append({
            "readiness": state[0],
            "needs_human": state[1],
            "escalate_pause": str(pause),
            "escalate_notify": str(notify),
            "answer": str(answer),
            "pause_minus_notify": str(pause - notify),
        })

    deltas = [Fraction(r["pause_minus_notify"]) for r in rows]
    dominated = all(d > 0 for d in deltas)
    if not dominated:
        raise AbstentionError(
            "escalate_pause is not strictly costlier than escalate_notify in every "
            "state, so sections 4 and 5 need a per-state breakdown that this script "
            "does not produce. The cost matrix changed; stop and re-derive.")

    return {
        "by_state": rows,
        "pause_costs_strictly_more_than_notify_in_every_state": dominated,
        "smallest_pause_penalty": str(min(deltas)),
        "largest_pause_penalty": str(max(deltas)),
        "consequence_for_cost": (
            "Any rule that turns an escalate_notify into an escalate_pause raises "
            "realised cost on every case it touches, by between "
            f"{min(deltas)} and {max(deltas)} per case. No belief set and no tau "
            "changes that; it is arithmetic on the matrix."),
        "consequence_for_misses": (
            "is_escalation counts both escalate actions, so a notify-to-pause "
            "rewrite cannot change the miss count. Only a rule that converts a "
            "non-escalation into a pause can, and it can only lower it."),
        "what_remains_empirical": (
            "How many cases each rule touches, and whether the misses it avoids are "
            "worth the pause penalty it pays. That is what sections 3 to 6 measure."),
    }


# --------------------------------------------------------------------------- #
# 2. H(b) and the tau grid
# --------------------------------------------------------------------------- #

def h_of(row: dict) -> float:
    """`H(b)` in bits: the joint entropy of the widened two-part belief, unquantised.

    Computed with `answer_model.joint_entropy`, the same function that produced the
    committed `results/answer-model.json` `h_joint` column, so the published arm
    reproduces that column exactly. Recomputed per arm rather than read from that
    file, because the committed column is on published beliefs only and `H(b)` moves
    when `b_h` moves.
    """
    b = Belief.from_dict(row["belief"])
    return am.joint_entropy(widen(b.readiness, b.needs_human))


def h_quantized(row: dict) -> float:
    """`H(b)` rounded to `H_DECIMALS`, which is what every threshold sees.

    Everything that compares against tau uses this. `h_of` is kept for the two
    places that must see the unquantised number: the agreement check against the
    committed `h_joint` column, and the measurement of how much noise the rounding
    absorbs.
    """
    return round(h_of(row), H_DECIMALS)


def float_noise(rows: list[dict]) -> dict:
    """What the quantisation absorbs and what it preserves, measured on this arm.

    The classification does not use the tolerance, which would be circular: gaps are
    called noise if they fall below a bound derived from double precision — eight
    ulp at the largest `H(b)` on the arm, which covers a six-term sum and its
    accumulation — and signal otherwise. The tolerance then has to sit strictly
    between the two, and both ends are checked rather than asserted.
    """
    raw = sorted(h_of(r) for r in rows)
    noise_bound = 8.0 * math.ulp(max(abs(v) for v in raw))
    gaps = [b - a for a, b in zip(raw, raw[1:]) if b != a]
    noise = [g for g in gaps if g < noise_bound]
    signal = [g for g in gaps if g >= noise_bound]
    tolerance = 10.0 ** -H_DECIMALS
    q = sorted({round(v, H_DECIMALS) for v in raw})

    if tolerance <= noise_bound:
        raise AbstentionError(
            f"the H(b) quantisation tolerance {tolerance:g} is not above the float "
            f"noise bound {noise_bound:g}, so it would not absorb the last-bit "
            "differences it exists for.")
    if signal and tolerance >= min(signal):
        raise AbstentionError(
            f"the H(b) quantisation tolerance {tolerance:g} is not below the "
            f"smallest genuine gap between distinct H(b) values ({min(signal):g}), "
            "so rounding would merge values that are really different. The belief "
            "set changed scale; re-derive H_DECIMALS rather than nudging it.")

    return {
        "h_decimals": H_DECIMALS,
        "tolerance": tolerance,
        "float_noise_bound": noise_bound,
        "n_distinct_before_quantising": len(set(raw)),
        "n_distinct_after_quantising": len(q),
        "n_spurious_distinctions_removed": len(set(raw)) - len(q),
        "n_gaps_below_the_noise_bound": len(noise),
        "largest_gap_absorbed": max(noise) if noise else None,
        "smallest_gap_preserved": min(signal) if signal else None,
        "margin_below_signal": (min(signal) / tolerance) if signal else None,
        "margin_above_noise": tolerance / noise_bound,
    }


def committed_h_agreement(rows: list[dict]) -> dict:
    """The published arm against `results/answer-model.json`'s `h_joint` column."""
    payload = json.loads((ROOT / "results" / "answer-model.json")
                         .read_text(encoding="utf-8"))
    committed = {c["case_id"]: c["h_joint"] for c in payload["per_case"]["cases"]}
    missing = [r["case_id"] for r in rows if r["case_id"] not in committed]
    if missing:
        raise AbstentionError(
            f"{len(missing)} cases have no committed h_joint to check against")
    worst = max(abs(h_of(r) - committed[r["case_id"]]) for r in rows)
    if worst > EXACT:
        raise AbstentionError(
            f"recomputed H(b) disagrees with the committed h_joint column by "
            f"{worst:g}, above the {EXACT:g} float tolerance. Either widen() or "
            "joint_entropy() changed.")
    return {"n_compared": len(rows), "max_abs_delta": worst,
            "source": "results/answer-model.json per_case.cases[].h_joint",
            "note": ("The committed column is on published beliefs only, which is "
                     "why the other two arms recompute rather than read it.")}


def quantile(values: list[float], q: float) -> float:
    """Linear-interpolated quantile of a sample, the numpy-default convention.

    Written out rather than imported because the project is stdlib-only. Verified
    against the pre-registered decile table for the published arm.
    """
    if not values:
        raise AbstentionError("no values to take a quantile of")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def tau_grid(rows: list[dict]) -> dict:
    """The eleven decile thresholds for one arm, in quantiles and in bits."""
    h_all = [h_quantized(r) for r in rows]
    h_test = [h_quantized(r) for r in rows if r["split"] == CLAIM_SPLIT]
    grid = [{"quantile": q,
             "tau_bits": round(quantile(h_all, q), 4),
             "tau_bits_full": quantile(h_all, q)}
            for q in QUANTILES]
    return {
        "population": GRID_POPULATION,
        "n_in_population": len(h_all),
        "observed_min_bits": round(min(h_all), 6),
        "observed_max_bits": round(max(h_all), 6),
        "observed_median_bits": round(quantile(h_all, 0.5), 4),
        "n_cases_at_h_exactly_zero": sum(1 for v in h_all if v == 0.0),
        "grid": grid,
        "n_distinct_tau": len({g["tau_bits_full"] for g in grid}),
        "deciles_on_the_scored_half_for_reference": [
            round(quantile(h_test, q), 4) for q in QUANTILES],
        "why_quantiles_not_absolute_bits": (
            "The observed distribution is bunched. An absolute grid over the 0-2.585 "
            "bit theoretical range would put most of its points in a region holding "
            "almost no cases, which is the S4 failure mode this gate is checking "
            "for. Deciles make the step commensurate with the quantity by "
            "construction."),
        "declared_incomparability": (
            "Decile values are not comparable across arms in absolute bits, because "
            "H(b) shifts when b_h shifts. Compare arms at equal quantiles, or read "
            "the bit column and accept that the same quantile is a different "
            "threshold on each arm."),
        "repeated_tau_are_repeated_thresholds": (
            "A decile grid on a tied distribution repeats values. Where two "
            "quantiles give the same tau they give the same firing set and the same "
            "cost, and the rows are identical by construction rather than by "
            "coincidence."),
        "why_the_top_decile_can_fire_on_nothing": (
            "The grid is taken over all 100 cases and the scoring is on the 50 test "
            "cases. If an arm's highest-entropy case is a dev case, tau at the 100th "
            "percentile is above every test case and the firing set is empty. That "
            "is the population choice showing through, not a failed comparison."),
    }


# --------------------------------------------------------------------------- #
# 3. The baseline, which is variant (c)'s policy
# --------------------------------------------------------------------------- #

def baseline_action(row: dict, *, legacy_tie_break: bool) -> str:
    b = Belief.from_dict(row["belief"])
    return costs.choose_action(b, row.get("constraints") or (),
                              matrix=costs.COST,
                              legacy_tie_break=legacy_tie_break).action


def decisions_for(rows: list[dict], *, legacy_tie_break: bool) -> list[dict]:
    """One record per case: the myopic action, its realised cost, H(b), the labels."""
    out = []
    for row in rows:
        action = baseline_action(row, legacy_tie_break=legacy_tie_break)
        labels = row["labels"]
        constraints = tuple(row.get("constraints") or ())
        out.append({
            "case_id": row["case_id"],
            "split": row["split"],
            "constraints": list(constraints),
            "b_h": round(float(row["belief"]["needs_human"]), 6),
            "h_bits": round(h_quantized(row), 6),
            "h_bits_full": h_quantized(row),
            "needs_human": bool(labels["needs_human"]),
            "readiness_label": labels["readiness"],
            "action": action,
            "realised_cost": realised_cost(action, labels),
            "cost_if_escalate_pause": realised_cost("escalate_pause", labels),
            "cost_if_escalate_notify": realised_cost("escalate_notify", labels),
            "cost_if_answer": realised_cost("answer", labels),
            "answer_feasible": "no_direct_answer" not in constraints,
        })
    return out


def split_of(decisions: list[dict], split: str | None) -> list[dict]:
    if split is None:
        return list(decisions)
    return [d for d in decisions if d["split"] == split]


def baseline_report(decisions: list[dict], committed: dict) -> dict:
    """Baseline scores per split, with the test split checked against rebaseline.json.

    Agreement is checked rather than inherited. This script implements
    `realised_cost` in one line instead of importing `experiments/rebaseline.py`,
    because that module imports `costs` under a second module name and two copies of
    the cost matrix would be a silent hazard. The price of not sharing the code is
    that the numbers have to be compared, so they are.
    """
    test = score(split_of(decisions, "test"))
    dev = score(split_of(decisions, "dev"))
    both = score(decisions)

    fields = ("n", "total_cost", "mean_cost", "missed_escalations", "action_counts")
    mismatches = [f for f in fields
                  if f in committed and committed[f] != test[f]]
    if mismatches:
        raise AbstentionError(
            f"baseline does not reproduce the committed test-split score: "
            f"{mismatches} differ. computed={ {f: test[f] for f in mismatches} } "
            f"committed={ {f: committed[f] for f in mismatches} }. Either the arm "
            "loader changed or the cost matrix did.")

    return {
        "test_claim_split": test,
        "dev_in_sample": dev,
        "all_100": both,
        "reproduces_committed_test_split": True,
        "committed_test_split": {f: committed[f] for f in fields if f in committed},
    }


# --------------------------------------------------------------------------- #
# 4. Variant (b): the fallback rewrite, and how big it is
# --------------------------------------------------------------------------- #

def variant_b(decisions: list[dict]) -> dict:
    """`escalate_notify` becomes `escalate_pause`; nothing else moves.

    OQ2 wrote (b) as a narrow tie-break: prefer pause when `ask` lost only because
    `VoI <= 0`. Gate 1 showed `VoI <= 0` on every case and Gate 4 confirmed it on
    every arm, so the condition is satisfied everywhere and the rule is not narrow.
    Its scope is exactly the set of cases whose fallback was notify, and the point of
    this section is to put a number on that set rather than describe it.

    `answer` and `hold` decisions are untouched: the rule names `escalate_notify` as
    what it replaces, and widening it to other actions would be a different rule.
    It is also tau-independent — no threshold appears in it.
    """
    rewritten = []
    for d in decisions:
        new = dict(d)
        if d["action"] == "escalate_notify":
            new["action"] = "escalate_pause"
            new["realised_cost"] = d["cost_if_escalate_pause"]
        rewritten.append(new)

    out = {"tau_independent": True, "scope": "cases whose myopic action was "
                                             "escalate_notify"}
    for label, split in (("test_claim_split", "test"), ("dev_in_sample", "dev"),
                         ("all_100", None)):
        base = split_of(decisions, split)
        new = split_of(rewritten, split)
        b_score, n_score = score(base), score(new)
        changed = [x["case_id"] for x, y in zip(base, new)
                   if x["action"] != y["action"]]
        out[label] = {
            **n_score,
            "n_actions_changed": len(changed),
            "fraction_of_cases_rewritten": round(len(changed) / len(base), 4),
            "delta_total_cost_vs_baseline": round(
                n_score["total_cost"] - b_score["total_cost"], 2),
            "delta_mean_cost_vs_baseline": round(
                n_score["mean_cost"] - b_score["mean_cost"], 4),
            "delta_missed_escalations_vs_baseline": (
                n_score["missed_escalations"] - b_score["missed_escalations"]),
        }
        if out[label]["delta_missed_escalations_vs_baseline"] != 0:
            raise AbstentionError(
                "variant (b) changed the miss count, which is impossible under "
                "is_escalation counting both escalate actions. Either the miss "
                "definition changed or the rewrite touched a non-notify action.")
    return out


# --------------------------------------------------------------------------- #
# 5. Variant (a): the H(b) threshold override
# --------------------------------------------------------------------------- #

def apply_override(decisions: list[dict], tau: float) -> list[dict]:
    """`H(b) >= tau` forces `escalate_pause`, whatever the matrix said.

    `escalate_pause` is feasible on every case: `no_direct_answer` is the only
    constraint in `src.costs.CONSTRAINT_FORBIDS` and it forbids `answer` alone. So
    the override never has to be skipped for feasibility, and there is no silent
    subset.
    """
    out = []
    for d in decisions:
        new = dict(d)
        if d["h_bits_full"] >= tau:
            new["action"] = "escalate_pause"
            new["realised_cost"] = d["cost_if_escalate_pause"]
        out.append(new)
    return out


def variant_a(decisions: list[dict], grid: dict) -> dict:
    """Scores at all eleven decile thresholds, per split."""
    out = {"tau_independent": False,
           "rule": "H(b) >= tau implies escalate_pause, overriding the matrix"}
    for label, split in (("test_claim_split", "test"), ("dev_in_sample", "dev"),
                         ("all_100", None)):
        base = split_of(decisions, split)
        b_score = score(base)
        per_tau = []
        for g in grid["grid"]:
            tau = g["tau_bits_full"]
            new = apply_override(base, tau)
            n_score = score(new)
            firing = [x["case_id"] for x in base if x["h_bits_full"] >= tau]
            changed = [x["case_id"] for x, y in zip(base, new)
                       if x["action"] != y["action"]]
            d_cost = round(n_score["total_cost"] - b_score["total_cost"], 2)
            d_miss = n_score["missed_escalations"] - b_score["missed_escalations"]
            per_tau.append({
                "quantile": g["quantile"],
                "tau_bits": g["tau_bits"],
                "n_firing": len(firing),
                "fraction_firing": round(len(firing) / len(base), 4),
                "n_actions_changed": len(changed),
                "total_cost": n_score["total_cost"],
                "mean_cost": n_score["mean_cost"],
                "missed_escalations": n_score["missed_escalations"],
                "action_counts": n_score["action_counts"],
                "delta_total_cost_vs_baseline": d_cost,
                "delta_mean_cost_vs_baseline": round(
                    n_score["mean_cost"] - b_score["mean_cost"], 4),
                "delta_missed_escalations_vs_baseline": d_miss,
                # Cost paid per miss avoided. The matrix already prices a miss, so
                # a positive number here means the pauses cost more than the misses
                # they removed were costing.
                "cost_per_miss_avoided": (round(d_cost / -d_miss, 2)
                                          if d_miss < 0 else None),
            })
        best = min(per_tau, key=lambda r: (r["total_cost"], -r["quantile"]))
        beats = [r["quantile"] for r in per_tau
                 if r["delta_total_cost_vs_baseline"] < 0]
        out[label] = {
            "per_tau": per_tau,
            "baseline_total_cost": b_score["total_cost"],
            "baseline_missed_escalations": b_score["missed_escalations"],
            "beats_baseline_at_any_tau": bool(beats),
            "quantiles_that_beat_baseline": beats,
            "cheapest_tau_on_this_split": {
                "quantile": best["quantile"], "tau_bits": best["tau_bits"],
                "total_cost": best["total_cost"],
                "delta_total_cost_vs_baseline":
                    best["delta_total_cost_vs_baseline"],
                "note": ("Reported because the grid was pre-registered before any "
                         "of these numbers existed. It is not a selected tau: no "
                         "value here was chosen to make a variant look good, and "
                         "picking the argmin on the split being scored would be "
                         "selection on the test half."),
            },
        }
    return out


# --------------------------------------------------------------------------- #
# 6. Variant (c), and the pause-against-notify-against-answer resolution table
# --------------------------------------------------------------------------- #

def variant_c(decisions: list[dict], grid: dict, baseline: dict) -> dict:
    """Abstention reported, never acted on: the firing set with the policy unchanged.

    Cost is the baseline cost at every tau, by construction rather than by
    measurement, so the per-tau rows carry the firing count and the cost columns are
    stated as identities. What (c) buys is the flag; what it costs is nothing.
    """
    out = {"tau_independent": False,
           "rule": "myopic argmin; H(b) >= tau is recorded as an abstention flag "
                   "and never changes the action",
           "cost_equals_baseline_by_construction": True}
    for label, split in (("test_claim_split", "test"), ("dev_in_sample", "dev"),
                         ("all_100", None)):
        base = split_of(decisions, split)
        b_score = score(base)
        per_tau = []
        for g in grid["grid"]:
            tau = g["tau_bits_full"]
            firing = [x for x in base if x["h_bits_full"] >= tau]
            per_tau.append({
                "quantile": g["quantile"],
                "tau_bits": g["tau_bits"],
                "n_flagged": len(firing),
                "fraction_flagged": round(len(firing) / len(base), 4),
                "n_flagged_that_need_a_human": sum(1 for x in firing
                                                   if x["needs_human"]),
                "n_flagged_the_baseline_already_escalates": sum(
                    1 for x in firing if is_escalation(x["action"])),
                "total_cost": b_score["total_cost"],
                "missed_escalations": b_score["missed_escalations"],
                "delta_total_cost_vs_baseline": 0.0,
                "delta_missed_escalations_vs_baseline": 0,
            })
        out[label] = {"per_tau": per_tau,
                      "action_counts": b_score["action_counts"],
                      "total_cost": b_score["total_cost"],
                      "mean_cost": b_score["mean_cost"],
                      "missed_escalations": b_score["missed_escalations"]}
    if out["test_claim_split"]["total_cost"] != \
            baseline["test_claim_split"]["total_cost"]:
        raise AbstentionError("variant (c) diverged from the baseline it is defined "
                              "to equal")
    return out


def resolution_table(decisions: list[dict], grid: dict) -> dict:
    """For every case abstention could fire on, pause against notify against answer.

    Sorted by `H(b)` descending, so the firing set at any tau is a prefix of this
    table and one table serves all eleven thresholds. That is what makes "abstention
    should resolve to pause" a measured claim about this matrix and these labels
    rather than a definition.

    The `answer` column is a counterfactual on an action some cases forbid. Those
    rows carry `answer_feasible: false` and are excluded from the `answer`
    aggregate, with the exclusion counted rather than dropped.
    """
    test = sorted(split_of(decisions, "test"),
                  key=lambda d: (-d["h_bits_full"], d["case_id"]))
    cases = [{k: d[k] for k in ("case_id", "b_h", "h_bits", "needs_human",
                                "readiness_label", "action", "realised_cost",
                                "cost_if_escalate_pause", "cost_if_escalate_notify",
                                "cost_if_answer", "answer_feasible", "constraints")}
             for d in test]

    per_tau = []
    for g in grid["grid"]:
        tau = g["tau_bits_full"]
        firing = [d for d in test if d["h_bits_full"] >= tau]
        feasible_answer = [d for d in firing if d["answer_feasible"]]
        per_tau.append({
            "quantile": g["quantile"],
            "tau_bits": g["tau_bits"],
            "n_firing": len(firing),
            "sum_cost_if_all_resolved_to_escalate_pause": round(
                sum(d["cost_if_escalate_pause"] for d in firing), 2),
            "sum_cost_if_all_resolved_to_escalate_notify": round(
                sum(d["cost_if_escalate_notify"] for d in firing), 2),
            "sum_baseline_cost_on_the_firing_set": round(
                sum(d["realised_cost"] for d in firing), 2),
            # The three-way comparison, on the one subset where all three actions
            # are available. Summing `answer` over the whole firing set and pause
            # over the whole firing set would compare different case sets.
            "n_answer_feasible": len(feasible_answer),
            "n_excluded_from_the_three_way_as_answer_infeasible": (
                len(firing) - len(feasible_answer)),
            "three_way_on_answer_feasible_subset": {
                "escalate_pause": round(
                    sum(d["cost_if_escalate_pause"] for d in feasible_answer), 2),
                "escalate_notify": round(
                    sum(d["cost_if_escalate_notify"] for d in feasible_answer), 2),
                "answer": round(
                    sum(d["cost_if_answer"] for d in feasible_answer), 2),
            },
        })

    return {
        "split": CLAIM_SPLIT,
        "ordering": "H(b) descending, so any tau's firing set is a prefix",
        "n_cases": len(cases),
        "n_answer_infeasible_on_this_split": sum(
            1 for d in test if not d["answer_feasible"]),
        "cases": cases,
        "per_tau_aggregate": per_tau,
        "how_to_read_the_answer_column": (
            "The `answer` column is the cost of resolving an uncertain case by "
            "answering anyway, which is the alternative abstention exists to avoid. "
            "Cases carrying no_direct_answer cannot answer at all, so the "
            "three-way comparison is taken on the answer-feasible subset of each "
            "firing set and the excluded count is reported next to it."),
    }


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def tie_break_sensitivity(rows: list[dict]) -> dict:
    """Whether the fresh tie-break rule changes any baseline action, per split.

    `results/run.json` was produced with the legacy rule and the fresh arms use
    safest-first, so this is not idle. On the test split the two agree on every arm,
    which is what lets the test-split baseline be compared against the committed
    scores. On dev they do not always agree, so the dev columns in this artifact are
    the fresh rule's actions and not run.json's recorded ones. Stated rather than
    left as a discrepancy for a reader to trip over.
    """
    out = {}
    for label, split in (("test_claim_split", "test"), ("dev_in_sample", "dev"),
                         ("all_100", None)):
        sub = [r for r in rows if split is None or r["split"] == split]
        fresh = [baseline_action(r, legacy_tie_break=False) for r in sub]
        legacy = [baseline_action(r, legacy_tie_break=True) for r in sub]
        differing = [{"case_id": r["case_id"], "fresh": x, "legacy": y}
                     for r, x, y in zip(sub, fresh, legacy) if x != y]
        out[label] = {"n_actions_differing": len(differing),
                      "cases": differing,
                      "matters": bool(differing)}
    out["why_the_test_split_is_the_one_that_has_to_agree"] = (
        "The committed scores this artifact checks itself against are test-split "
        "scores. Where the two rules differ on dev, the dev columns here report the "
        "fresh rule and run.json reports the legacy one.")
    return out


def build_report() -> dict:
    committed = json.loads(REBASELINE_JSON.read_text(encoding="utf-8"))

    arms: dict = {}
    for arm in ARMS:
        rows, source = vc.load_arm(arm)
        if len(rows) != 100:
            raise AbstentionError(f"arm {arm!r} has {len(rows)} rows, expected 100")
        grid = tau_grid(rows)
        decisions = decisions_for(rows, legacy_tie_break=FRESH_LEGACY_TIE_BREAK)
        top, key = COMMITTED_BASELINE[arm]
        ref = committed[top][key]
        base = baseline_report(decisions, ref)
        arms[arm] = {
            "source": source,
            "float_noise": float_noise(rows),
            "tau_grid": grid,
            "baseline": base,
            "tie_break_sensitivity": tie_break_sensitivity(rows),
            "variants": {
                "c_diagnostic": variant_c(decisions, grid, base),
                "b_fallback_ordering": variant_b(decisions),
                "a_threshold_override": variant_a(decisions, grid),
            },
            "resolution_counterfactual": resolution_table(decisions, grid),
        }
        if arm == "published":
            arms[arm]["h_agreement_with_committed_column"] = (
                committed_h_agreement(rows))

    return {
        "what_this_is": (
            "The realised cost of all three OQ2 abstention variants, on three belief "
            "arms, over the pre-registered decile grid for tau. Abstention resolves "
            "to escalate_pause."),
        "beliefs": {
            "arms": list(ARMS),
            "n_cases_per_arm": 100,
            "claim_split": CLAIM_SPLIT,
            "why_three_arms_not_four": (
                "rebaselined would add a column about cache drift, which abstention "
                "has nothing to do with "
                "(decisions/v2-gate4-preregistration.md section 5.1)."),
            "dev_is_in_sample": (
                "The isotonic map was fitted on dev, so calibrated b_h on the dev "
                "half is in-sample. Dev numbers are shown and labelled; no claim "
                "rests on them."),
        },
        "matrix_facts": matrix_facts(),
        "arms": arms,
        "the_call": {
            "status": "open at the time this artifact was written",
            "made_by": "Kaps, at the Gate 4 close, on these numbers",
            "pre_commitment": (
                "tau was defined as deciles before any of these costs existed, and "
                "no variant was tuned. If (a) or (b) beats (c) on realised cost that "
                "is reported plainly here, whatever it does to the "
                "no-free-parameters claim."),
            "what_this_script_does_not_do": (
                "It does not recommend a variant. The measurement and the "
                "recommendation are kept separate so they cannot be read as one "
                "thing."),
        },
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _sign(x) -> str:
    return f"+{x}" if x > 0 else f"{x}"


def render(report: dict) -> str:
    out: list[str] = []
    w = out.append

    w("# The cost of abstention: three variants, three arms")
    w("")
    b = report["beliefs"]
    w(f"Beliefs: {b['n_cases_per_arm']} cases per arm, arms "
      f"{', '.join('`' + a + '`' for a in b['arms'])}. Claim split: "
      f"`{b['claim_split']}`; dev is in-sample and labelled.")
    w("")
    w(b["why_three_arms_not_four"])
    w("")
    for arm in report["arms"]:
        w(f"- `{arm}` — {report['arms'][arm]['source']}")
    w("")

    m = report["matrix_facts"]
    w("## 1. What the cost matrix settles first")
    w("")
    w("| readiness | needs_human | `escalate_pause` | `escalate_notify` | "
      "`answer` | pause − notify |")
    w("|---|---|---:|---:|---:|---:|")
    for r in m["by_state"]:
        w(f"| {r['readiness']} | {r['needs_human']} | {r['escalate_pause']} | "
          f"{r['escalate_notify']} | {r['answer']} | "
          f"+{r['pause_minus_notify']} |")
    w("")
    w(m["consequence_for_cost"])
    w("")
    w(m["consequence_for_misses"])
    w("")
    w(m["what_remains_empirical"])
    w("")

    w("## 2. The tau grid")
    w("")
    first = report["arms"][b["arms"][0]]["tau_grid"]
    w(f"Population: {first['n_in_population']} cases of the arm being scored. "
      "Deciles, 0% to 100%.")
    w("")
    header = "| quantile | " + " | ".join(f"`{a}` bits" for a in b["arms"]) + " |"
    w(header)
    w("|---|" + "---:|" * len(b["arms"]))
    for i, q in enumerate(QUANTILES):
        cells = " | ".join(
            f"{report['arms'][a]['tau_grid']['grid'][i]['tau_bits']:.4f}"
            for a in b["arms"])
        w(f"| {q:.1f} | {cells} |")
    w("")
    w("| arm | min | median | max | distinct tau | cases at H = 0 |")
    w("|---|---:|---:|---:|---:|---:|")
    for a in b["arms"]:
        g = report["arms"][a]["tau_grid"]
        w(f"| `{a}` | {g['observed_min_bits']:.6f} | "
          f"{g['observed_median_bits']:.4f} | {g['observed_max_bits']:.6f} | "
          f"{g['n_distinct_tau']} | {g['n_cases_at_h_exactly_zero']} |")
    w("")
    w(first["why_quantiles_not_absolute_bits"])
    w("")
    w(first["declared_incomparability"])
    w("")
    w(first["repeated_tau_are_repeated_thresholds"])
    w("")
    w("`H(b)` is quantised to 12 decimals before any comparison against tau. Cases "
      "with the same belief can differ in the last bit of the entropy sum, and left "
      "alone that made two identical deciles read as different thresholds. What the "
      "rounding absorbs and what it preserves, per arm:")
    w("")
    w("| arm | distinct H before | after | spurious removed | largest gap absorbed | "
      "smallest gap preserved | margin below signal |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for a in b["arms"]:
        f = report["arms"][a]["float_noise"]
        absorbed = ("—" if f["largest_gap_absorbed"] is None
                    else f"{f['largest_gap_absorbed']:.2e}")
        kept = ("—" if f["smallest_gap_preserved"] is None
                else f"{f['smallest_gap_preserved']:.2e}")
        margin = ("—" if f["margin_below_signal"] is None
                  else f"{f['margin_below_signal']:.1e}x")
        w(f"| `{a}` | {f['n_distinct_before_quantising']} | "
          f"{f['n_distinct_after_quantising']} | "
          f"{f['n_spurious_distinctions_removed']} | {absorbed} | {kept} | "
          f"{margin} |")
    w("")
    f0 = report["arms"][b["arms"][0]]["float_noise"]
    w(f"The tolerance is {f0['tolerance']:.0e} bits. It has to sit above the float "
      f"noise bound ({f0['float_noise_bound']:.2e}, eight ulp at the largest "
      "`H(b)`) so it absorbs last-bit differences, and below the smallest genuine "
      "gap so it merges nothing real. Both ends are checked per arm, and gaps are "
      "classified by the noise bound rather than by the tolerance so the test is not "
      "circular.")
    w("")
    ha = report["arms"]["published"]["h_agreement_with_committed_column"]
    w(f"The published arm's recomputed `H(b)` agrees with {ha['source']} on all "
      f"{ha['n_compared']} cases, max absolute delta {ha['max_abs_delta']:g}. "
      f"{ha['note']}")
    w("")

    w("## 3. The baseline, which is what (c) leaves in place")
    w("")
    w("Test split. Checked against `results/rebaseline.json` rather than trusted "
      "because it shares definitions with it.")
    w("")
    w("| arm | total cost | mean cost | misses | action counts | reproduces "
      "committed |")
    w("|---|---:|---:|---:|---|---|")
    for a in b["arms"]:
        s = report["arms"][a]["baseline"]
        t = s["test_claim_split"]
        w(f"| `{a}` | {t['total_cost']} | {t['mean_cost']} | "
          f"{t['missed_escalations']} | `{t['action_counts']}` | "
          f"{s['reproduces_committed_test_split']} |")
    w("")
    w("Dev split, in-sample:")
    w("")
    w("| arm | total cost | mean cost | misses | action counts |")
    w("|---|---:|---:|---:|---|")
    for a in b["arms"]:
        d = report["arms"][a]["baseline"]["dev_in_sample"]
        w(f"| `{a}` | {d['total_cost']} | {d['mean_cost']} | "
          f"{d['missed_escalations']} | `{d['action_counts']}` |")
    w("")
    w("| arm | tie-break changes actions on test | on dev | cases |")
    w("|---|---|---|---|")
    for a in b["arms"]:
        tb = report["arms"][a]["tie_break_sensitivity"]
        cases = ", ".join(f"`{c['case_id']}` {c['legacy']} to {c['fresh']}"
                          for c in tb["all_100"]["cases"]) or "—"
        w(f"| `{a}` | {tb['test_claim_split']['matters']} | "
          f"{tb['dev_in_sample']['matters']} | {cases} |")
    w("")
    w(report["arms"][b["arms"][0]]["tie_break_sensitivity"][
        "why_the_test_split_is_the_one_that_has_to_agree"])
    w("")

    w("## 4. Variant (b): the fallback rewrite")
    w("")
    vb = report["arms"][b["arms"][0]]["variants"]["b_fallback_ordering"]
    w("`VoI <= 0` holds on every case on every arm, so \"`ask` lost only because "
      "`VoI <= 0`\" is true everywhere and (b) is not a tie-break. Its scope is "
      f"{vb['scope']}. It is tau-independent.")
    w("")
    w("| arm | cases rewritten | fraction | total cost | delta | mean cost | "
      "misses | delta |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|")
    for a in b["arms"]:
        v = report["arms"][a]["variants"]["b_fallback_ordering"]["test_claim_split"]
        w(f"| `{a}` | {v['n_actions_changed']} | "
          f"{v['fraction_of_cases_rewritten']:.2f} | {v['total_cost']} | "
          f"{_sign(v['delta_total_cost_vs_baseline'])} | {v['mean_cost']} | "
          f"{v['missed_escalations']} | "
          f"{_sign(v['delta_missed_escalations_vs_baseline'])} |")
    w("")
    w("The miss delta is zero on every arm, and it has to be: both actions count as "
      "escalations, so no notify-to-pause rewrite can change a miss. (b) buys "
      "nothing measurable on the miss axis and pays the pause penalty on every case "
      "it touches.")
    w("")

    w("## 5. Variant (a): the H(b) threshold override")
    w("")
    w("`H(b) >= tau` forces `escalate_pause`. `escalate_pause` is feasible on every "
      "case, so no firing is ever skipped.")
    w("")
    w(first["why_the_top_decile_can_fire_on_nothing"])
    w("")
    for a in b["arms"]:
        va = report["arms"][a]["variants"]["a_threshold_override"]
        t = va["test_claim_split"]
        w(f"### `{a}` — baseline {t['baseline_total_cost']} cost, "
          f"{t['baseline_missed_escalations']} misses")
        w("")
        w("| quantile | tau bits | firing | changed | total cost | delta | misses | "
          "delta | cost per miss avoided |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in t["per_tau"]:
            cpm = ("—" if r["cost_per_miss_avoided"] is None
                   else f"{r['cost_per_miss_avoided']}")
            w(f"| {r['quantile']:.1f} | {r['tau_bits']:.4f} | {r['n_firing']} | "
              f"{r['n_actions_changed']} | {r['total_cost']} | "
              f"{_sign(r['delta_total_cost_vs_baseline'])} | "
              f"{r['missed_escalations']} | "
              f"{_sign(r['delta_missed_escalations_vs_baseline'])} | {cpm} |")
        w("")
        c = t["cheapest_tau_on_this_split"]
        w(f"Beats baseline at any tau on this split: "
          f"{t['beats_baseline_at_any_tau']}. Cheapest grid point: quantile "
          f"{c['quantile']:.1f} ({c['tau_bits']:.4f} bits), cost "
          f"{c['total_cost']}, {_sign(c['delta_total_cost_vs_baseline'])} against "
          f"baseline. {c['note']}")
        w("")

    w("## 6. Variant (c): the flag, and what it would have cost to act")
    w("")
    w("Cost is the baseline cost at every tau, by construction. What varies is how "
      "many cases carry the flag and how many of those the baseline already "
      "escalates.")
    w("")
    for a in b["arms"]:
        vcv = report["arms"][a]["variants"]["c_diagnostic"]["test_claim_split"]
        w(f"### `{a}`")
        w("")
        w("| quantile | tau bits | flagged | of those, need a human | of those, "
          "already escalated |")
        w("|---|---:|---:|---:|---:|")
        for r in vcv["per_tau"]:
            w(f"| {r['quantile']:.1f} | {r['tau_bits']:.4f} | {r['n_flagged']} | "
              f"{r['n_flagged_that_need_a_human']} | "
              f"{r['n_flagged_the_baseline_already_escalates']} |")
        w("")

    w("## 7. Resolving a firing case: pause against notify against answer")
    w("")
    rc0 = report["arms"][b["arms"][0]]["resolution_counterfactual"]
    w(f"Test split, {rc0['ordering']}. {rc0['how_to_read_the_answer_column']} "
      f"{rc0['n_answer_infeasible_on_this_split']} of the "
      f"{rc0['n_cases']} test cases carry it.")
    w("")
    for a in b["arms"]:
        rc = report["arms"][a]["resolution_counterfactual"]
        w(f"### `{a}`")
        w("")
        w("Whole firing set:")
        w("")
        w("| quantile | firing | all pause | all notify | baseline on the firing "
          "set |")
        w("|---|---:|---:|---:|---:|")
        for r in rc["per_tau_aggregate"]:
            w(f"| {r['quantile']:.1f} | {r['n_firing']} | "
              f"{r['sum_cost_if_all_resolved_to_escalate_pause']} | "
              f"{r['sum_cost_if_all_resolved_to_escalate_notify']} | "
              f"{r['sum_baseline_cost_on_the_firing_set']} |")
        w("")
        w("Three-way, on the answer-feasible subset of each firing set:")
        w("")
        w("| quantile | answer-feasible | excluded | `escalate_pause` | "
          "`escalate_notify` | `answer` |")
        w("|---|---:|---:|---:|---:|---:|")
        for r in rc["per_tau_aggregate"]:
            t3 = r["three_way_on_answer_feasible_subset"]
            w(f"| {r['quantile']:.1f} | {r['n_answer_feasible']} | "
              f"{r['n_excluded_from_the_three_way_as_answer_infeasible']} | "
              f"{t3['escalate_pause']} | {t3['escalate_notify']} | "
              f"{t3['answer']} |")
        w("")

    w("## 8. The call")
    w("")
    tc = report["the_call"]
    w(f"Status: {tc['status']}. Made by {tc['made_by']}.")
    w("")
    w(tc["pre_commitment"])
    w("")
    w(tc["what_this_script_does_not_do"])
    w("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--json", type=Path, help="write the findings here")
    ap.add_argument("--md", type=Path, help="write the rendered report here")
    args = ap.parse_args()

    report = build_report()
    text = render(report)
    print(text)

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str),
                             encoding="utf-8")
        print(f"wrote {args.json}")
    if args.md:
        args.md.write_text(text, encoding="utf-8")
        print(f"wrote {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
