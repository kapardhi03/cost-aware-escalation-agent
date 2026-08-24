#!/usr/bin/env python3
"""Re-baseline the v1 policy on the freshly-elicited beliefs, three arms.

Why this exists. The temperature-0 reproduction check found 11 of 100 written
`needs_human` values differ from v1's cached beliefs, so the beliefs v1's published
numbers were computed on cannot be reproduced today. (What moved is not knowable
from the record — v1 stored the model alias it requested, not the snapshot the API
resolved to. See limitation L10.) A naive "v1 was 1.720/16, v2 is X" comparison
would therefore mix two different effects: the recalibration map, and whatever
changed between the cache dates. This script separates them by holding the belief
source fixed within a comparison and varying one thing at a time.

Three arms, all scored on the test split with v1's own cost matrix and v1's own
miss definition:

  1. published        — v1's committed numbers, from the OLD belief cache. Context only.
                        Read from results/run.json, never recomputed.
  2. rebaselined      — v1's decision rule on the FRESH beliefs, using the digit
                        the model wrote, exactly as v1 parsed it. Differs from (1)
                        only by the belief cache, so (1) vs (2) isolates DRIFT.
  3. raw / calibrated — the continuous elicited score, before and after the
                        isotonic map. Both on the fresh beliefs with identical
                        fresh readiness, so raw vs calibrated isolates the MAP.
                        This is the clean calibration-only before/after.

Arms 2 and 3 share the same fresh readiness vector; they differ only in what
supplies `needs_human`. That is what makes each contrast one-variable.

Makes no API calls. Reads the committed caches and refuses if they are absent or
were produced from stub payloads.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import belief as belief_mod          # noqa: E402
import calibrate as calib            # noqa: E402
import costs as costs_mod            # noqa: E402
import elicit as elicit_mod          # noqa: E402

logger = logging.getLogger("rebaseline")

CASES_PATH = PROJECT_ROOT / "data" / "cases.json"
RUN_PATH = PROJECT_ROOT / "results" / "run.json"
ELICIT_PATH = PROJECT_ROOT / "results" / "logprob-elicitation.json"
RESULTS_DIR = PROJECT_ROOT / "results"

#: The claim split. Selection happened on dev; every number here is test.
CLAIM_SPLIT = "test"

#: run.json was produced with the legacy tie-break, and robustness.py asserts that
#: the legacy path reproduces it exactly. On the test split both tie-break rules
#: give identical actions, costs and misses, so the arms below are not sensitive
#: to the choice — verified in `tie_break_sensitivity` and reported, not assumed.
FRESH_LEGACY_TIE_BREAK = False


class RebaselineError(RuntimeError):
    """A precondition failed. Never downgraded to a warning."""


# --------------------------------------------------------------------------- #
# Scoring — v1's definitions, imported rather than restated
# --------------------------------------------------------------------------- #

def realised_cost(action: str, labels: dict) -> float:
    """Identical to run_policies.realised_cost: score with the real matrix."""
    return costs_mod.COST[action][(labels["readiness"], labels["needs_human"])]


def is_escalation(action: str) -> bool:
    """v1 counts either escalate action as an escalation (run_policies.summarise)."""
    return action.startswith("escalate")


def score_arm(decisions: list[dict]) -> dict:
    """Aggregate one arm exactly as run_policies.summarise does.

    `missed_escalations` is a false negative: the case needed a human and the
    policy did not escalate. Precision and recall use the same tp/fp/fn.
    """
    n = len(decisions)
    total = sum(d["realised_cost"] for d in decisions)
    tp = sum(1 for d in decisions if is_escalation(d["action"]) and d["needs_human"])
    fp = sum(1 for d in decisions if is_escalation(d["action"]) and not d["needs_human"])
    fn = sum(1 for d in decisions if not is_escalation(d["action"]) and d["needs_human"])
    return {
        "n": n,
        "total_cost": round(total, 2),
        "mean_cost": round(total / n, 4),
        "missed_escalations": fn,
        "escalation_precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "escalation_recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
        "action_counts": dict(sorted(Counter(d["action"] for d in decisions).items())),
    }


def decide(readiness: dict, needs_human: float, constraints, *,
           legacy_tie_break: bool) -> str:
    """One decision under v1's cost-aware policy."""
    b = belief_mod.Belief(readiness=dict(readiness), needs_human=float(needs_human))
    return costs_mod.choose_action(
        b, constraints, matrix=costs_mod.COST,
        legacy_tie_break=legacy_tie_break).action


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

def load_fresh_beliefs(cache_path: Path) -> dict:
    """Parse every elicitor-A payload back into a Belief via v1's own parser.

    Uses `belief.to_belief`, the same function v1 used on the same JSON shape, so
    the readiness vector and written digit here are what v1 would have recorded
    had it run today. Not a reimplementation.
    """
    cache = elicit_mod.load_cache(cache_path)
    out = {}
    for key, entry in cache["entries"].items():
        if entry["elicitor"] != elicit_mod.ELICITOR_A:
            continue
        raw = json.loads(entry["payload"]["text"])
        b = belief_mod.to_belief(raw)
        out[entry["case_id"]] = {
            "readiness": b.readiness,
            "written_needs_human": b.needs_human,
            "model": entry["model"],
        }
    return out


def load_elicitation(path: Path) -> dict:
    """The committed Gate 2 results, with the provenance guards enforced."""
    if not path.exists():
        raise RebaselineError(
            f"{path.name} is absent. Run experiments/build_logprob_cache.py first; "
            "this script never calls the API itself.")
    r = json.loads(path.read_text(encoding="utf-8"))
    if not r.get("reportable"):
        raise RebaselineError(
            f"{path.name} is marked not reportable ({r.get('stub_rows')} stub rows). "
            "Re-baselining stub payloads would produce a number that looks like a "
            "measurement and is not one.")
    if r.get("stub_rows"):
        raise RebaselineError(
            f"{path.name} contains {r['stub_rows']} stub rows.")
    return r


def rebuild_map(elicitation: dict):
    """Reconstruct the chosen calibration map from the committed knots.

    Refitting here would be a second fit, and a second fit is a second chance to
    land on different parameters. The map that was selected is the map that gets
    applied, so it is read back from the stored knots and then verified against
    the recalibrated scores the driver already wrote.
    """
    cal = elicitation["analysis"]["calibration"]
    spec = cal["map"]
    name = spec["name"]
    if name == "isotonic":
        m = calib.IsotonicMap(knots=tuple(tuple(k) for k in spec["knots"]), name=name)
    elif name == "platt":
        m = calib.PlattMap(a=spec["a"], b=spec["b"], name=name)
    elif name == "identity":
        m = calib.IdentityMap()
    else:
        raise RebaselineError(f"unknown map {name!r} in {ELICIT_PATH.name}")

    # Verify the reconstruction reproduces what the driver recorded, to 1e-12.
    worst, worst_case = 0.0, None
    for case_id, rec in elicitation["analysis"]["recalibrated_scores"].items():
        got = calib.apply_map(m, [rec["raw"]])[0]
        d = abs(got - rec["calibrated"])
        if d > worst:
            worst, worst_case = d, case_id
    if worst > 1e-12:
        raise RebaselineError(
            f"the reconstructed {name} map does not reproduce the committed "
            f"recalibrated scores (worst delta {worst:.3e} at {worst_case}). The "
            "stored knots and the stored scores disagree; one of them is stale.")
    return m, worst


# --------------------------------------------------------------------------- #
# The three arms
# --------------------------------------------------------------------------- #

def build_arms(cases, fresh, elicitation, cal_map, *, legacy_tie_break: bool) -> dict:
    """Decisions per arm, on the claim split, one variable at a time."""
    raw_by_case = {cid: rec["raw"]
                   for cid, rec in elicitation["analysis"]["recalibrated_scores"].items()}
    cal_by_case = {cid: rec["calibrated"]
                   for cid, rec in elicitation["analysis"]["recalibrated_scores"].items()}

    arms = {"rebaselined_written": [], "fresh_raw": [], "fresh_calibrated": []}
    for case in cases:
        if case["split"] != CLAIM_SPLIT:
            continue
        cid = case["case_id"]
        if cid not in fresh:
            raise RebaselineError(f"{cid} has no elicitor-A payload in the cache")
        readiness = fresh[cid]["readiness"]
        constraints = case.get("constraints", [])
        labels = case["labels"]

        for arm, value in (
            ("rebaselined_written", fresh[cid]["written_needs_human"]),
            ("fresh_raw", raw_by_case[cid]),
            ("fresh_calibrated", cal_by_case[cid]),
        ):
            action = decide(readiness, value, constraints,
                            legacy_tie_break=legacy_tie_break)
            arms[arm].append({
                "case_id": cid,
                "action": action,
                "needs_human": bool(labels["needs_human"]),
                "realised_cost": realised_cost(action, labels),
                "value": round(float(value), 6),
            })
    return arms


def tie_break_sensitivity(cases, fresh, elicitation) -> dict:
    """Does the tie-break rule change any arm? Reported rather than assumed."""
    out = {}
    for legacy in (True, False):
        m, _ = rebuild_map(elicitation)
        arms = build_arms(cases, fresh, elicitation, m, legacy_tie_break=legacy)
        out["legacy" if legacy else "fixed"] = {
            k: score_arm(v) for k, v in arms.items()}
    same = all(out["legacy"][k]["mean_cost"] == out["fixed"][k]["mean_cost"]
               and out["legacy"][k]["missed_escalations"] == out["fixed"][k]["missed_escalations"]
               for k in out["legacy"])
    return {"identical": same, "by_rule": out}


def published_baseline(run_path: Path) -> dict:
    """v1's committed numbers, read not recomputed. From the OLD belief cache."""
    r = json.loads(run_path.read_text(encoding="utf-8"))
    ca_test = r["summaries"][CLAIM_SPLIT]["policies"]["cost_aware"]
    ca_all = r["summaries"]["all"]["policies"]["cost_aware"]
    return {
        "test": {k: ca_test[k] for k in
                 ("mean_cost", "missed_escalations", "total_cost", "action_counts")},
        "all_100_reference": {k: ca_all[k] for k in
                              ("mean_cost", "missed_escalations", "total_cost")},
    }


def belief_free_reference(run_path: Path) -> dict:
    """The trivial policies, whose numbers are drift-invariant by construction.

    `always_notify` and friends ignore the belief entirely, so their realised cost
    is a function of the labels alone. Model drift cannot move them. That makes
    them the one baseline in this file that compares across cache dates without a
    caveat, and the right yardstick for asking whether an arm that escalates
    almost everything is actually doing better than escalating everything.
    """
    r = json.loads(run_path.read_text(encoding="utf-8"))
    pol = r["summaries"][CLAIM_SPLIT]["policies"]
    return {
        name: {k: pol[name][k] for k in
               ("mean_cost", "missed_escalations", "total_cost", "action_counts")}
        for name in ("always_notify", "always_answer")
    }


def drift_on_test(run_path: Path, arms_raw: dict) -> dict:
    """Per-case comparison of v1's committed test decisions against the fresh ones.

    The aggregate drift contrast comes out to zero change, which on its own would
    read as "the drift did not matter". At the case level it is not zero: several
    written values moved, some of them across a decision boundary, and the cost
    deltas happen to cancel. Recording the per-case detail is what stops the
    aggregate from being read as a stability result it is not.
    """
    r = json.loads(run_path.read_text(encoding="utf-8"))
    labels = {row["case_id"]: bool(row["labels"]["needs_human"]) for row in r["rows"]}
    v1 = {row["case_id"]: row["decisions"]["cost_aware"]
          for row in r["rows"] if row["split"] == CLAIM_SPLIT}
    v1_value = {row["case_id"]: row["belief"]["needs_human"]
                for row in r["rows"] if row["split"] == CLAIM_SPLIT}
    fresh = {d["case_id"]: d for d in arms_raw["rebaselined_written"]}

    if set(v1) != set(fresh):
        raise RebaselineError(
            "the committed test split and the re-baselined test split cover "
            f"different cases ({len(v1)} vs {len(fresh)})")

    moved, changed = [], []
    for cid in sorted(v1):
        before, after = v1_value[cid], fresh[cid]["value"]
        if abs(before - after) <= 1e-9:
            continue
        rec = {
            "case_id": cid,
            "needs_human_value": {"v1": before, "fresh": after},
            "action": {"v1": v1[cid]["action"], "fresh": fresh[cid]["action"]},
            "realised_cost": {"v1": v1[cid]["realised_cost"],
                              "fresh": fresh[cid]["realised_cost"]},
            "label_needs_human": labels[cid],
            "action_changed": v1[cid]["action"] != fresh[cid]["action"],
        }
        moved.append(rec)
        if rec["action_changed"]:
            changed.append(rec)

    def missing(decisions_by_case, action_of) -> set:
        return {cid for cid in decisions_by_case
                if not is_escalation(action_of(cid)) and labels[cid]}

    miss_v1 = missing(v1, lambda c: v1[c]["action"])
    miss_fresh = missing(fresh, lambda c: fresh[c]["action"])

    return {
        "cases_compared": len(v1),
        "values_moved": len(moved),
        "actions_changed": len(changed),
        "cost_delta_sum": round(sum(r["realised_cost"]["fresh"]
                                    - r["realised_cost"]["v1"] for r in changed), 4),
        "detail": moved,
        "missed_escalation_sets": {
            "n_v1": len(miss_v1),
            "n_fresh": len(miss_fresh),
            "identical_cases": miss_v1 == miss_fresh,
            "fixed_by_drift": sorted(miss_v1 - miss_fresh),
            "introduced_by_drift": sorted(miss_fresh - miss_v1),
        },
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

SECONDARY_CAVEAT = calib.PREREGISTRATION["secondary_caveat"]


def render(report: dict) -> str:
    L: list[str] = []
    A = L.append
    A("# Re-baseline — separating belief drift from the calibration map")
    A("")
    A(f"Generated {report['generated_at']} · split `{CLAIM_SPLIT}` · n = {report['n']}"
      f" · no API calls")
    A("")
    A("The temperature-0 reproduction check found "
      f"**{report['drift']['drifted']} of {report['drift']['compared']}** written "
      f"`needs_human` values differ from v1's cached beliefs "
      f"({report['drift']['match_rate']:.0%} match). The beliefs v1's published numbers "
      "were computed on cannot be reproduced today, so a direct comparison against those "
      "numbers would mix the calibration map with whatever changed between the cache "
      "dates. Each contrast below varies one thing.")
    A("")

    A("## The three arms")
    A("")
    A("| arm | beliefs | `needs_human` from | mean cost | missed esc. | escalates |")
    A("| --- | --- | --- | ---: | ---: | ---: |")
    p = report["published"]["test"]
    n = report["n"]
    pub_esc = sum(v for k, v in p["action_counts"].items() if k.startswith("escalate"))
    A(f"| published (v1, committed) | v1 cache | written digit | {p['mean_cost']:.4f} | "
      f"{p['missed_escalations']} | {pub_esc}/{n} |")
    for key, label, src in (
        ("rebaselined_written", "re-baselined", "written digit"),
        ("fresh_raw", "raw continuous", "logprob expectation"),
        ("fresh_calibrated", "calibrated", f"{report['map_name']}(raw)"),
    ):
        s = report["arms"][key]
        esc = sum(v for k, v in s["action_counts"].items() if k.startswith("escalate"))
        A(f"| {label} | **fresh** | {src} | {s['mean_cost']:.4f} | "
          f"{s['missed_escalations']} | {esc}/{n} |")
    ref = report["belief_free_reference"]["always_notify"]
    A(f"| _always_notify (reference)_ | _none_ | _ignores the belief_ | "
      f"_{ref['mean_cost']:.4f}_ | _{ref['missed_escalations']}_ | _{n}/{n}_ |")
    A("")
    A("The last row is a trivial policy that escalates unconditionally. It never reads "
      "a belief, so its realised cost is a function of the labels alone and no amount of "
      "belief drift can move it — the one number here that compares across cache dates "
      "with no caveat. It is included because an arm that escalates most of the split has "
      "to be measured against escalating all of it.")
    A("")

    A("## What each contrast isolates")
    A("")
    d = report["contrasts"]["drift"]
    dt = report["drift_on_test"]
    A(f"**Belief drift across cache dates** — published vs re-baselined, both the written "
      f"digit, the belief source the only difference: mean cost {d['from']:.4f} → "
      f"{d['to']:.4f} ({d['mean_cost_delta']:+.4f}), missed escalations "
      f"{d['missed_from']} → {d['missed_to']} ({d['missed_delta']:+d}).")
    A("")
    A(f"**That aggregate zero is a coincidence, not stability.** On the claim split "
      f"{dt['values_moved']} written values moved and {dt['actions_changed']} of them "
      f"crossed a decision boundary; the realised-cost deltas of those "
      f"{dt['actions_changed']} sum to exactly {dt['cost_delta_sum']:g}, and the "
      f"action counts cancel term for term. The miss count is unchanged at "
      f"{dt['missed_escalation_sets']['n_v1']} but "
      f"`identical_cases: "
      f"{str(dt['missed_escalation_sets']['identical_cases']).lower()}` — drift fixed "
      f"{', '.join('`%s`' % c for c in dt['missed_escalation_sets']['fixed_by_drift'])} "
      f"and introduced "
      f"{', '.join('`%s`' % c for c in dt['missed_escalation_sets']['introduced_by_drift'])}"
      ". Read the aggregate as \"drift did not happen to move the totals here\", never "
      "as \"the beliefs are stable\".")
    A("")
    A("| case | `needs_human` v1 → fresh | action v1 → fresh | cost v1 → fresh |")
    A("| --- | ---: | --- | ---: |")
    for rec in dt["detail"]:
        v = rec["needs_human_value"]
        a = rec["action"]
        c = rec["realised_cost"]
        mark = "" if rec["action_changed"] else " _(no action change)_"
        A(f"| `{rec['case_id']}` | {v['v1']} → {v['fresh']} | "
          f"{a['v1']} → {a['fresh']}{mark} | {c['v1']} → {c['fresh']} |")
    A("")
    c = report["contrasts"]["calibration"]
    ra, ca_ = report["arms"]["fresh_raw"], report["arms"]["fresh_calibrated"]
    A(f"**The calibration map** — raw vs calibrated, same fresh beliefs, same fresh "
      f"readiness, the map the only difference: mean cost {c['from']:.4f} → "
      f"{c['to']:.4f} ({c['mean_cost_delta']:+.4f}), missed escalations "
      f"{c['missed_from']} → {c['missed_to']} ({c['missed_delta']:+d}).")
    A("")
    A(f"**The two secondary metrics move in opposite directions.** Calibration cuts "
      f"misses from {c['missed_from']} to {c['missed_to']} and raises mean cost by "
      f"{c['mean_cost_delta']:+.4f}. The mechanism is visible in the action counts: the "
      f"map lifts the low scores enough that the myopic rule escalates "
      f"{sum(v for k, v in ca_['action_counts'].items() if k.startswith('escalate'))} "
      f"of {n} cases instead of "
      f"{sum(v for k, v in ra['action_counts'].items() if k.startswith('escalate'))}, "
      f"so escalation recall rises ({ra['escalation_recall']} → "
      f"{ca_['escalation_recall']}) while precision falls ({ra['escalation_precision']} "
      f"→ {ca_['escalation_precision']}). Better-calibrated probabilities move the "
      "operating point along the cost/miss trade-off; they do not dominate the "
      "uncalibrated arm on both metrics at once. That is a finding about the fixed cost "
      "matrix and the one-step rule, not a defect in the map, and it is why the Gate 2 "
      "claim is the calibration metrics rather than the cost proxy.")
    A("")
    A("The second contrast is the calibration-only before/after. The first is "
      "reported so the drift is visible and is never attributed to the map.")
    A("")

    A("## These are the secondary metrics")
    A("")
    A(f"> {SECONDARY_CAVEAT}")
    A("")
    A("The Gate 2 claim is the held-out calibration result, not these numbers:")
    h = report["calibration_claim"]
    A("")
    A("| metric | raw | calibrated |")
    A("| --- | ---: | ---: |")
    A(f"| cross-entropy (bits) | {h['raw']['cross_entropy_bits']:.4f} | "
      f"{h['calibrated']['cross_entropy_bits']:.4f} |")
    A(f"| ECE | {h['raw']['ece']:.4f} | {h['calibrated']['ece']:.4f} |")
    A(f"| Brier | {h['raw']['brier']:.4f} | {h['calibrated']['brier']:.4f} |")
    A("")

    A("## Limitations, recorded")
    A("")
    A(f"- **Temperature-0 reproduction is {report['drift']['match_rate']:.0%}, not 100%.** "
      f"{report['drift']['drifted']} of {report['drift']['compared']} cases wrote a "
      "different value than v1 cached, at temperature 0 with a byte-identical prompt. "
      "The cause is not determinable from the record: both runs asked for the alias "
      "`gpt-4o-mini`, but v1 stored the alias it requested while v2 stores the snapshot "
      "the API resolved to, so a snapshot change between the two cache dates and "
      "serving-side nondeterminism at temperature 0 are equally consistent with the "
      "evidence. `temperature=0` pins the sampler, not the weights. Recorded as "
      "limitation L10; the fix applied from v2 on is to store the resolved model id. "
      "Every cross-date comparison in this project inherits the limit.")
    A(f"- **The test split carries only 8 of v1's 16 missed escalations**, so a change "
      "of one or two misses is inside noise and is not evidence. The calibration "
      f"contrast moves {abs(report['contrasts']['calibration']['missed_delta'])}, which "
      "is past that floor — but it arrives with a mean-cost increase and a precision "
      "drop, so it is a shift in operating point, not a free improvement.")
    A(f"- **The aggregate drift contrast is zero by coincidence.** "
      f"{report['drift_on_test']['actions_changed']} actions changed and their costs "
      "cancelled. The per-case table above is the honest version; the aggregate row is "
      "not evidence that the beliefs are stable.")
    A(f"- **Ordering is not preserved on test** "
      f"(`order_preserved_on_test: {str(report['order_preserved_on_test']).lower()}`). "
      "The isotonic map merges distinct scores by construction. Carried forward as an "
      "open flag for the value-of-information ceiling, which reads the ordering.")
    ts = report["tie_break_sensitivity"]
    A(f"- **Tie-break rule does not move these numbers** (`identical: "
      f"{str(ts['identical']).lower()}`): both the legacy and fixed tie-break give the "
      "same mean cost and miss count on every arm, so the drift contrast is not an "
      "artefact of that choice.")
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)-7s %(name)s: %(message)s")

    try:
        elicitation = load_elicitation(ELICIT_PATH)
        cache_path = elicit_mod.logprob_cache_path()
        if not cache_path.exists():
            raise RebaselineError(
                f"{cache_path} is absent; this script reads the cache and never calls.")
        fresh = load_fresh_beliefs(cache_path)
        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
        cal_map, map_delta = rebuild_map(elicitation)
    except (RebaselineError, elicit_mod.ElicitationError) as exc:
        print(f"Cannot re-baseline:\n\n  {exc}\n", file=sys.stderr)
        return 2

    arms_raw = build_arms(cases, fresh, elicitation, cal_map,
                          legacy_tie_break=FRESH_LEGACY_TIE_BREAK)
    arms = {k: score_arm(v) for k, v in arms_raw.items()}
    pub = published_baseline(RUN_PATH)
    cal = elicitation["analysis"]["calibration"]

    def contrast(a_name, a, b_name, b):
        return {
            "from": a["mean_cost"], "to": b["mean_cost"],
            "mean_cost_delta": round(b["mean_cost"] - a["mean_cost"], 4),
            "missed_from": a["missed_escalations"], "missed_to": b["missed_escalations"],
            "missed_delta": b["missed_escalations"] - a["missed_escalations"],
            "arms": [a_name, b_name],
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "split": CLAIM_SPLIT,
        "n": arms["fresh_calibrated"]["n"],
        "reportable": True,
        "calls": 0,
        "map_name": cal["map"]["name"],
        "map_reconstruction_max_delta": map_delta,
        "order_preserved_on_test": cal["order_preserved_on_test"],
        "model_summary": elicitation["model_summary"],
        "published": pub,
        "belief_free_reference": belief_free_reference(RUN_PATH),
        "drift_on_test": drift_on_test(RUN_PATH, arms_raw),
        "arms": arms,
        "arm_decisions": arms_raw,
        "contrasts": {
            "drift": contrast("published", pub["test"],
                              "rebaselined_written", arms["rebaselined_written"]),
            "calibration": contrast("fresh_raw", arms["fresh_raw"],
                                    "fresh_calibrated", arms["fresh_calibrated"]),
        },
        "calibration_claim": {
            "raw": cal["test_raw"], "calibrated": cal["test_calibrated"],
        },
        "drift": {k: elicitation["reproduction_check"][k]
                  for k in ("compared", "matched", "drifted", "match_rate")},
        "tie_break_sensitivity": tie_break_sensitivity(cases, fresh, elicitation),
        "secondary_caveat": SECONDARY_CAVEAT,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    j = args.out / "rebaseline.json"
    m = args.out / "rebaseline.md"
    j.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = render(report)
    m.write_text(text + "\n", encoding="utf-8")
    print()
    print(text)
    print(f"\nwrote {j}\nwrote {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
