"""
run_policies.py — score the cost-aware policy against the uniform baseline.

Usage
    python experiments/run_policies.py                  # real run, needs API keys
    python experiments/run_policies.py --dry-run        # offline, NOT reportable
    python experiments/run_policies.py --split test     # report on one half only

What it does, in order: load the cases, fetch a belief per case (from the cache
when present, from the LLM when not), run every policy over those identical
beliefs, score each decision against the case's true labels, and write the
numbers to results/.

Three design points worth stating, because each one would invalidate the
comparison if done the other way.

1. BOTH policies are scored with the REAL cost matrix. The baseline *decides*
   with uniform costs, but its mistakes are priced with the practitioner's costs,
   exactly like the cost-aware policy's. Scoring each policy under its own matrix
   would compare two different rulers and prove nothing.

2. Both policies read the SAME beliefs. The belief comes from the cache, is
   fetched once, and is handed to every policy unchanged. Any difference in the
   results is therefore attributable to the cost matrix and to nothing else.

3. The reported run must be LLM-only. A cache mixing LLM beliefs with keyword
   beliefs cannot support a calibration claim, so the run refuses to report
   unless every belief came from a real model. --dry-run lifts that, and stamps
   the output NOT REPORTABLE so a stray file cannot be mistaken for a result.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import belief as belief_mod          # noqa: E402
import config as config_mod          # noqa: E402
import costs as costs_mod            # noqa: E402

logger = logging.getLogger("run_policies")

CASES_PATH = PROJECT_ROOT / "data" / "cases.json"
RESULTS_DIR = PROJECT_ROOT / "results"

#: Policies under test. Each is (name, decision matrix). Scoring always uses the
#: real matrix regardless of which one the policy decided with.
POLICIES = {
    "cost_aware": costs_mod.COST,
    "uniform_baseline": costs_mod.UNIFORM_COST,
}

#: Degenerate references. Not policies anyone would ship — they exist to show the
#: case set is not trivially won. If "always_notify" beats the cost-aware policy,
#: the set is too escalation-heavy and the headline result means nothing.
TRIVIAL = ("always_answer", "always_notify", "always_ask")


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

def realised_cost(action: str, labels: dict) -> float:
    """What an action actually cost, given the case's true hidden state."""
    state = (labels["readiness"], labels["needs_human"])
    return costs_mod.COST[action][state]


def trivial_action(name: str, constraints) -> str:
    """A fixed action, still subject to the hard constraint."""
    wanted = {"always_answer": "answer", "always_notify": "escalate_notify",
              "always_ask": "ask"}[name]
    feasible = costs_mod.feasible_actions(constraints)
    # Even a degenerate policy cannot break a hard constraint; it falls back to
    # notify, which is what a system with the rule but no belief would do.
    return wanted if wanted in feasible else "escalate_notify"


def expected_calibration_error(pairs, bins: int = 10) -> dict:
    """ECE over (predicted probability, observed outcome) pairs.

    Equal-width bins. Reports per-bin detail as well as the summary, because a
    single ECE number hides whether the model is over- or under-confident.
    """
    if not pairs:
        return {"ece": None, "n": 0, "bins": []}

    buckets = defaultdict(list)
    for p, outcome in pairs:
        idx = min(int(p * bins), bins - 1)
        buckets[idx].append((p, outcome))

    total, ece, detail = len(pairs), 0.0, []
    for idx in range(bins):
        members = buckets.get(idx, [])
        if not members:
            continue
        mean_p = sum(p for p, _ in members) / len(members)
        observed = sum(1 for _, o in members if o) / len(members)
        ece += (len(members) / total) * abs(mean_p - observed)
        detail.append({"bin": f"{idx / bins:.1f}-{(idx + 1) / bins:.1f}",
                       "n": len(members), "mean_predicted": round(mean_p, 4),
                       "observed_frequency": round(observed, 4),
                       "gap": round(mean_p - observed, 4)})
    return {"ece": round(ece, 4), "n": total, "bins": detail}


# --------------------------------------------------------------------------- #
# The run
# --------------------------------------------------------------------------- #

def run(settings, cases, allow_non_llm: bool, legacy_tie_break: bool = False) -> dict:
    rows, non_llm = [], 0

    for case in cases:
        b, meta = belief_mod.get_belief(
            case["case_id"], case["message"],
            context=belief_mod.CaseContext.from_dict(case.get("context")),
            settings=settings,
        )
        if not meta.is_llm:
            non_llm += 1

        constraints = case.get("constraints", [])
        row = {
            "case_id": case["case_id"], "archetype": case["archetype"],
            "variant": case["variant"], "split": case["split"],
            "labels": case["labels"], "constraints": constraints,
            "provider": meta.provider,
            "belief": {"readiness": {k: round(v, 6) for k, v in b.readiness.items()},
                       "needs_human": round(b.needs_human, 6)},
            "decisions": {},
        }

        for name, matrix in POLICIES.items():
            decision = costs_mod.choose_action(
                b, constraints, matrix=matrix, legacy_tie_break=legacy_tie_break)
            row["decisions"][name] = {
                "action": decision.action,
                "realised_cost": realised_cost(decision.action, case["labels"]),
                "margin": None if math.isinf(decision.margin) else round(decision.margin, 4),
                "constraint_bound": decision.constrained,
            }
        for name in TRIVIAL:
            action = trivial_action(name, constraints)
            row["decisions"][name] = {
                "action": action,
                "realised_cost": realised_cost(action, case["labels"]),
                "margin": None, "constraint_bound": False,
            }
        rows.append(row)

    if non_llm and not allow_non_llm:
        raise belief_mod.BeliefSourceError(
            f"{non_llm} of {len(rows)} beliefs are not LLM-derived, so these "
            "numbers cannot support a calibration claim. Re-run with "
            "BELIEF_ALLOW_RULE_FALLBACK=false and real keys, or pass --dry-run "
            "to produce clearly-marked non-reportable output."
        )
    return {"rows": rows, "non_llm": non_llm}


def summarise(rows, split=None) -> dict:
    subset = [r for r in rows if split is None or r["split"] == split]
    if not subset:
        return {}

    policies = list(POLICIES) + list(TRIVIAL)
    out = {"n": len(subset), "policies": {}}

    for name in policies:
        actions = [r["decisions"][name]["action"] for r in subset]
        costs_seen = [r["decisions"][name]["realised_cost"] for r in subset]

        # Escalation quality: treat either escalate action as "escalated".
        tp = sum(1 for r in subset if r["decisions"][name]["action"].startswith("escalate")
                 and r["labels"]["needs_human"])
        fp = sum(1 for r in subset if r["decisions"][name]["action"].startswith("escalate")
                 and not r["labels"]["needs_human"])
        fn = sum(1 for r in subset if not r["decisions"][name]["action"].startswith("escalate")
                 and r["labels"]["needs_human"])

        violations = sum(
            1 for r in subset
            if r["constraints"] and r["decisions"][name]["action"] == "answer")

        out["policies"][name] = {
            "total_cost": round(sum(costs_seen), 2),
            "mean_cost": round(sum(costs_seen) / len(subset), 4),
            "action_counts": dict(sorted(Counter(actions).items())),
            "escalation_precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
            "escalation_recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
            "missed_escalations": fn,
            "constraint_violations": violations,
        }

    a, b = "cost_aware", "uniform_baseline"
    disagree = [r["case_id"] for r in subset
                if r["decisions"][a]["action"] != r["decisions"][b]["action"]]
    out["comparison"] = {
        "disagreements": len(disagree),
        "disagreement_rate": round(len(disagree) / len(subset), 4),
        "cost_delta": round(out["policies"][a]["total_cost"]
                            - out["policies"][b]["total_cost"], 2),
        "disagreement_case_ids": disagree[:20],
    }

    out["calibration"] = {
        "needs_human": expected_calibration_error(
            [(r["belief"]["needs_human"], r["labels"]["needs_human"]) for r in subset]),
        "readiness_argmax": expected_calibration_error(
            [(max(r["belief"]["readiness"].values()),
              max(r["belief"]["readiness"], key=r["belief"]["readiness"].get)
              == r["labels"]["readiness"]) for r in subset]),
    }

    per_archetype = {}
    for archetype in sorted({r["archetype"] for r in subset}):
        members = [r for r in subset if r["archetype"] == archetype]
        per_archetype[str(archetype)] = {
            "n": len(members),
            "cost_aware": round(sum(r["decisions"][a]["realised_cost"]
                                    for r in members) / len(members), 3),
            "uniform_baseline": round(sum(r["decisions"][b]["realised_cost"]
                                          for r in members) / len(members), 3),
        }
    out["per_archetype_mean_cost"] = per_archetype
    return out


def render(report: dict) -> str:
    L = ["# Policy run — results", ""]
    if not report["reportable"]:
        L += ["> **NOT REPORTABLE.** Beliefs are not all LLM-derived. These numbers",
              "> exist to prove the pipeline runs; they must not appear in the paper.", ""]
    L += [f"Generated {report['generated_at']} · provider `{report['provider_summary']}` · "
          f"{report['n_cases']} cases", ""]

    for split in ("dev", "test", None):
        s = report["summaries"][split or "all"]
        if not s:
            continue
        L += [f"## {(split or 'all').upper()} — n={s['n']}", "",
              "| policy | total cost | mean | missed esc. | precision | recall | violations |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for name, p in s["policies"].items():
            L.append(f"| {'**' + name + '**' if name in POLICIES else name} | "
                     f"{p['total_cost']} | {p['mean_cost']} | {p['missed_escalations']} | "
                     f"{p['escalation_precision']} | {p['escalation_recall']} | "
                     f"{p['constraint_violations']} |")
        c = s["comparison"]
        L += ["", f"Disagreements: **{c['disagreements']}** ({c['disagreement_rate']:.0%}) · "
                  f"cost delta (cost-aware − baseline): **{c['cost_delta']}**", "",
              f"ECE `needs_human`: **{s['calibration']['needs_human']['ece']}** · "
              f"ECE readiness (argmax): {s['calibration']['readiness_argmax']['ece']}", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="offline keyword beliefs; output is marked NOT REPORTABLE")
    ap.add_argument("--split", choices=("dev", "test"), help="restrict the run")
    ap.add_argument("--legacy-tie-break", action="store_true",
                    help="resolve exact cost ties in ACTIONS order (toward `answer`) "
                         "instead of safest-first. Reproduces the committed "
                         "results/run.json and the paper's Table 2, which were "
                         "generated before the tie-break was corrected; the "
                         "difference is one case and 0.07 mean cost.")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)-7s %(name)s: %(message)s")

    if args.dry_run:
        os.environ.setdefault("BELIEF_PROVIDER", "rule")
        os.environ.setdefault("BELIEF_ALLOW_RULE_FALLBACK", "true")
        # A dry run MUST NOT write into the real cache. get_belief is read-through
        # and keyed by case_id, so keyword beliefs left in the reportable cache
        # would be returned to a later live run, which would then never call the
        # LLM and would silently report keyword numbers as model numbers. Caught
        # the first time this script was exercised: the offline run had already
        # filled data/belief_cache.json with 100 rule-derived entries.
        os.environ["BELIEF_CACHE_PATH"] = str(PROJECT_ROOT / "data" / "belief_cache_DRY.json")

    try:
        settings = config_mod.load_settings(reload=True)
    except config_mod.ConfigError as exc:
        print(f"Configuration is not usable:\n\n  {exc}\n", file=sys.stderr)
        return 1

    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if args.split is None or c["split"] == args.split]
    logger.info("Loaded %d cases from %s", len(cases), CASES_PATH.name)

    try:
        result = run(settings, cases, allow_non_llm=args.dry_run,
                     legacy_tie_break=args.legacy_tie_break)
    except belief_mod.BeliefSourceError as exc:
        print(f"\nRun refused:\n\n  {exc}\n", file=sys.stderr)
        return 2

    rows = result["rows"]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reportable": result["non_llm"] == 0,
        "n_cases": len(rows),
        "provider_summary": ", ".join(f"{k}={v}" for k, v in
                                      sorted(Counter(r["provider"] for r in rows).items())),
        "cost_matrix": {a: {f"{r}|{h}": c for (r, h), c in row.items()}
                        for a, row in costs_mod.COST.items()},
        "summaries": {"dev": summarise(rows, "dev"), "test": summarise(rows, "test"),
                      "all": summarise(rows)},
        "rows": rows,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    stem = "run" if result["non_llm"] == 0 else "run_DRY"
    (args.out / f"{stem}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.out / f"{stem}.md").write_text(render(report), encoding="utf-8")

    print("\n" + render(report))
    print(f"\nwrote {args.out / (stem + '.json')}")
    print(f"wrote {args.out / (stem + '.md')}")

    total_violations = sum(p["constraint_violations"]
                           for s in report["summaries"].values() if s
                           for p in s["policies"].values())
    if total_violations:
        print(f"\nFAIL: {total_violations} hard-constraint violations", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
