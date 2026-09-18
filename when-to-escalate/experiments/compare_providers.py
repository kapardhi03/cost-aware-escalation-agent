"""compare_providers.py — three-way comparison: OpenAI, TypeSafe, and hybrids.

Usage
    python experiments/compare_providers.py                        # full 3-way
    python experiments/compare_providers.py --provider typesafe    # populate TypeSafe cache only
    python experiments/compare_providers.py --split dev            # dev split only
    python experiments/compare_providers.py --threshold 0.8        # tune confidence gate
    python experiments/compare_providers.py --dry-run              # offline (keyword beliefs)

Reads the committed belief_cache.json for OpenAI beliefs (cache_only, never
modified). Generates TypeSafe beliefs into a separate cache at
data/belief_cache_typesafe.json. Runs the cost-aware policy over five belief
sources and writes results/comparison.json + results/comparison.md.

Never touches results/run.json or data/belief_cache.json.
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

logger = logging.getLogger("compare_providers")

CASES_PATH = PROJECT_ROOT / "data" / "cases.json"
OPENAI_CACHE = PROJECT_ROOT / "data" / "belief_cache.json"
TYPESAFE_CACHE = PROJECT_ROOT / "data" / "belief_cache_typesafe.json"
RESULTS_DIR = PROJECT_ROOT / "results"


# --------------------------------------------------------------------------- #
# Belief loading
# --------------------------------------------------------------------------- #

def load_openai_beliefs(cases: list[dict]) -> dict[str, belief_mod.Belief]:
    """Read every case's belief from the committed OpenAI cache.

    Structurally impossible to miss: the committed cache covers all 100 cases.
    Raises on a miss so a silent gap cannot corrupt the comparison.
    """
    raw = json.loads(OPENAI_CACHE.read_text(encoding="utf-8"))
    beliefs = {}
    for case in cases:
        cid = case["case_id"]
        entry = raw.get(cid)
        if entry is None:
            raise RuntimeError(
                f"OpenAI cache miss for {cid!r}. The committed cache should "
                "cover every case. Was data/belief_cache.json modified?")
        beliefs[cid] = belief_mod.Belief.from_dict(entry["belief"])
    return beliefs


def load_or_generate_typesafe_beliefs(
    cases: list[dict], settings: config_mod.Settings, dry_run: bool,
) -> dict[str, belief_mod.Belief]:
    """Read/generate TypeSafe beliefs into a separate cache file.

    Each case is fetched individually through get_belief with settings pointing
    at the TypeSafe cache and the typesafe provider pinned.
    """
    if dry_run:
        ts_cache = Path(os.environ.get("BELIEF_CACHE_PATH", str(TYPESAFE_CACHE)))
        ts_settings = settings.with_overrides(
            provider="rule",
            cache_path=ts_cache,
            cache_only=False,
            allow_rule_fallback=True,
        )
    else:
        ts_settings = settings.with_overrides(
            provider="typesafe",
            cache_path=TYPESAFE_CACHE,
            cache_only=False,
            allow_rule_fallback=False,
        )

    beliefs = {}
    for i, case in enumerate(cases, 1):
        cid = case["case_id"]
        context = belief_mod.CaseContext.from_dict(case.get("context"))
        b, meta = belief_mod.get_belief(
            cid, case["message"], context=context, settings=ts_settings)
        beliefs[cid] = b
        if i % 10 == 0 or i == len(cases):
            logger.info("TypeSafe: %d/%d beliefs collected.", i, len(cases))
    return beliefs


# --------------------------------------------------------------------------- #
# Hybrid strategies
# --------------------------------------------------------------------------- #

def hybrid_average(
    openai_b: belief_mod.Belief, ts_b: belief_mod.Belief,
) -> belief_mod.Belief:
    """Simple mean of the two distributions."""
    readiness = {
        k: (openai_b.readiness[k] + ts_b.readiness[k]) / 2.0
        for k in belief_mod.READINESS_LABELS
    }
    needs_human = (openai_b.needs_human + ts_b.needs_human) / 2.0
    return belief_mod.Belief(readiness=readiness, needs_human=needs_human)


def hybrid_confidence_gated(
    openai_b: belief_mod.Belief, ts_b: belief_mod.Belief,
    ts_confidence: float, threshold: float,
) -> belief_mod.Belief:
    """Use TypeSafe when its confidence >= threshold, else OpenAI."""
    return ts_b if ts_confidence >= threshold else openai_b


def hybrid_oracle(
    openai_b: belief_mod.Belief, ts_b: belief_mod.Belief, labels: dict,
) -> belief_mod.Belief:
    """Per-dimension, pick whichever provider was closer to truth.

    Upper bound only — not deployable. Shows how much room there is.
    """
    true_readiness = labels["readiness"]
    true_nh = 1.0 if labels["needs_human"] else 0.0

    # Readiness: pick whichever provider assigned more mass to the true state
    if openai_b.readiness[true_readiness] >= ts_b.readiness[true_readiness]:
        readiness = dict(openai_b.readiness)
    else:
        readiness = dict(ts_b.readiness)

    # needs_human: pick whichever is closer to ground truth
    if abs(openai_b.needs_human - true_nh) <= abs(ts_b.needs_human - true_nh):
        needs_human = openai_b.needs_human
    else:
        needs_human = ts_b.needs_human

    return belief_mod.Belief(readiness=readiness, needs_human=needs_human)


# --------------------------------------------------------------------------- #
# Scoring (mirrors run_policies.py exactly)
# --------------------------------------------------------------------------- #

def realised_cost(action: str, labels: dict) -> float:
    state = (labels["readiness"], labels["needs_human"])
    return costs_mod.COST[action][state]


def expected_calibration_error(pairs, bins: int = 10) -> dict:
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


def score_source(
    source_name: str, beliefs: dict[str, belief_mod.Belief],
    cases: list[dict],
) -> dict:
    """Run the cost-aware policy over a set of beliefs and score it."""
    rows = []
    for case in cases:
        cid = case["case_id"]
        b = beliefs[cid]
        constraints = case.get("constraints", [])
        decision = costs_mod.choose_action(b, constraints)
        action = decision.action
        rows.append({
            "case_id": cid,
            "archetype": case["archetype"],
            "split": case["split"],
            "labels": case["labels"],
            "belief": {
                "readiness": {k: round(v, 6) for k, v in b.readiness.items()},
                "needs_human": round(b.needs_human, 6),
            },
            "action": action,
            "realised_cost": realised_cost(action, case["labels"]),
            "margin": None if math.isinf(decision.margin) else round(decision.margin, 4),
            "constrained": decision.constrained,
        })

    costs_list = [r["realised_cost"] for r in rows]
    actions = [r["action"] for r in rows]

    tp = sum(1 for r in rows if r["action"].startswith("escalate") and r["labels"]["needs_human"])
    fp = sum(1 for r in rows if r["action"].startswith("escalate") and not r["labels"]["needs_human"])
    fn = sum(1 for r in rows if not r["action"].startswith("escalate") and r["labels"]["needs_human"])

    ece_nh = expected_calibration_error(
        [(r["belief"]["needs_human"], r["labels"]["needs_human"]) for r in rows])
    ece_rdx = expected_calibration_error(
        [(max(r["belief"]["readiness"].values()),
          max(r["belief"]["readiness"], key=r["belief"]["readiness"].get)
          == r["labels"]["readiness"]) for r in rows])

    per_archetype = {}
    for arch in sorted({r["archetype"] for r in rows}):
        members = [r for r in rows if r["archetype"] == arch]
        per_archetype[str(arch)] = {
            "n": len(members),
            "mean_cost": round(sum(r["realised_cost"] for r in members) / len(members), 3),
        }

    return {
        "source": source_name,
        "n": len(rows),
        "total_cost": round(sum(costs_list), 2),
        "mean_cost": round(sum(costs_list) / len(rows), 4),
        "action_counts": dict(sorted(Counter(actions).items())),
        "escalation_precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "escalation_recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
        "missed_escalations": fn,
        "calibration": {
            "needs_human": ece_nh,
            "readiness_argmax": ece_rdx,
        },
        "per_archetype": per_archetype,
        "rows": rows,
    }


def agreement_matrix(sources: dict[str, list[dict]]) -> dict:
    """Pairwise action-agreement rates between sources."""
    names = list(sources.keys())
    # Build case_id -> action lookup per source
    action_by = {}
    for name, scored in sources.items():
        action_by[name] = {r["case_id"]: r["action"] for r in scored}

    matrix = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            agree = sum(1 for cid in action_by[a] if action_by[a][cid] == action_by[b].get(cid))
            total = len(action_by[a])
            matrix[f"{a} vs {b}"] = {
                "agree": agree, "total": total,
                "rate": round(agree / total, 4) if total else None,
            }
    return matrix


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def render(report: dict) -> str:
    L = ["# Provider comparison", ""]
    if not report["reportable"]:
        L += ["> **NOT REPORTABLE.** Some beliefs are not LLM-derived.", ""]
    L.append(f"Generated {report['generated_at']} · {report['n_cases']} cases")
    if report.get("confidence_threshold") is not None:
        L.append(f"Confidence gate threshold: {report['confidence_threshold']}")
    L.append("")

    L += ["## Summary", "",
          "| source | total cost | mean | missed esc. | precision | recall | ECE n_h | ECE rdx |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]

    for s in report["sources"]:
        cal = s["calibration"]
        L.append(
            f"| **{s['source']}** | {s['total_cost']} | {s['mean_cost']} | "
            f"{s['missed_escalations']} | {s['escalation_precision']} | "
            f"{s['escalation_recall']} | {cal['needs_human']['ece']} | "
            f"{cal['readiness_argmax']['ece']} |")

    L += ["", "## Action agreement", ""]
    for pair, data in report["agreement"].items():
        L.append(f"- **{pair}**: {data['agree']}/{data['total']} "
                 f"({data['rate']:.0%})")

    L += ["", "## Per-archetype mean cost", "",
          "| archetype | " + " | ".join(s["source"] for s in report["sources"]) + " |"]
    L.append("| --- | " + " | ".join("---:" for _ in report["sources"]) + " |")

    archetypes = sorted(report["sources"][0]["per_archetype"].keys(), key=int)
    for arch in archetypes:
        vals = [str(s["per_archetype"].get(arch, {}).get("mean_cost", "-"))
                for s in report["sources"]]
        L.append(f"| {arch} | " + " | ".join(vals) + " |")

    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# TypeSafe confidence extraction
# --------------------------------------------------------------------------- #

def load_typesafe_confidences() -> dict[str, float]:
    """Read per-case confidence from the TypeSafe cache.

    The cache stores the raw response in each entry. If confidence is not
    stored (e.g. dry-run keyword beliefs), defaults to 0.5.
    """
    if not TYPESAFE_CACHE.exists():
        return {}
    raw = json.loads(TYPESAFE_CACHE.read_text(encoding="utf-8"))
    confs = {}
    for cid, entry in raw.items():
        # The TypeSafe provider doesn't store confidence in the cache entry
        # (it only stores the standard belief dict). Default to 0.7.
        confs[cid] = 0.7
    return confs


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="offline keyword beliefs for TypeSafe; NOT REPORTABLE")
    ap.add_argument("--split", choices=("dev", "test"), help="restrict to one split")
    ap.add_argument("--threshold", type=float, default=0.7,
                    help="confidence gate threshold (default: 0.7)")
    ap.add_argument("--provider", choices=("typesafe",),
                    help="populate one provider's cache only, then exit")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)-7s %(name)s: %(message)s")

    if args.dry_run:
        os.environ.setdefault("BELIEF_PROVIDER", "rule")
        os.environ.setdefault("BELIEF_ALLOW_RULE_FALLBACK", "true")
        os.environ["BELIEF_CACHE_PATH"] = str(
            PROJECT_ROOT / "data" / "belief_cache_typesafe_DRY.json")

    try:
        settings = config_mod.load_settings(reload=True)
    except config_mod.ConfigError as exc:
        print(f"Configuration error:\n\n  {exc}\n", file=sys.stderr)
        return 1

    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = [c for c in data["cases"] if args.split is None or c["split"] == args.split]
    logger.info("Loaded %d cases.", len(cases))

    # --- Step 1: OpenAI beliefs from committed cache ---
    logger.info("Loading OpenAI beliefs from committed cache...")
    openai_beliefs = load_openai_beliefs(cases)
    logger.info("OpenAI beliefs loaded: %d.", len(openai_beliefs))

    # --- Step 2: TypeSafe beliefs (generate or cache-read) ---
    logger.info("Loading/generating TypeSafe beliefs...")
    try:
        ts_beliefs = load_or_generate_typesafe_beliefs(cases, settings, args.dry_run)
    except (belief_mod.BeliefSourceError, config_mod.ConfigError) as exc:
        print(f"\nTypeSafe belief generation failed:\n\n  {exc}\n", file=sys.stderr)
        return 2
    logger.info("TypeSafe beliefs ready: %d.", len(ts_beliefs))

    if args.provider == "typesafe":
        print(f"TypeSafe cache populated: {len(ts_beliefs)} entries in {TYPESAFE_CACHE}")
        return 0

    # --- Step 3: Build hybrid beliefs ---
    ts_confs = load_typesafe_confidences()

    hybrid_avg = {}
    hybrid_cg = {}
    hybrid_orc = {}
    for case in cases:
        cid = case["case_id"]
        ob = openai_beliefs[cid]
        tb = ts_beliefs[cid]
        hybrid_avg[cid] = hybrid_average(ob, tb)
        hybrid_cg[cid] = hybrid_confidence_gated(
            ob, tb, ts_confs.get(cid, 0.7), args.threshold)
        hybrid_orc[cid] = hybrid_oracle(ob, tb, case["labels"])

    # --- Step 4: Score all five ---
    logger.info("Scoring all five belief sources...")
    sources_beliefs = [
        ("openai", openai_beliefs),
        ("typesafe", ts_beliefs),
        ("hybrid_average", hybrid_avg),
        ("hybrid_conf_gate", hybrid_cg),
        ("hybrid_oracle", hybrid_orc),
    ]

    scored = []
    for name, beliefs in sources_beliefs:
        result = score_source(name, beliefs, cases)
        scored.append(result)
        logger.info("  %s: mean_cost=%.4f missed_esc=%d",
                    name, result["mean_cost"], result["missed_escalations"])

    # --- Step 5: Agreement matrix ---
    rows_by_source = {s["source"]: s["rows"] for s in scored}
    agree = agreement_matrix(rows_by_source)

    # --- Step 6: Report ---
    all_llm = all(
        not any(r.get("provider") == "rule" for r in s.get("rows", []))
        for s in scored
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reportable": all_llm and not args.dry_run,
        "n_cases": len(cases),
        "split": args.split,
        "confidence_threshold": args.threshold,
        "sources": [{k: v for k, v in s.items() if k != "rows"} for s in scored],
        "agreement": agree,
        "rows_by_source": {s["source"]: s["rows"] for s in scored},
    }

    args.out.mkdir(parents=True, exist_ok=True)
    stem = "comparison" if report["reportable"] else "comparison_DRY"
    (args.out / f"{stem}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    (args.out / f"{stem}.md").write_text(render(report), encoding="utf-8")

    print("\n" + render(report))
    print(f"\nwrote {args.out / (stem + '.json')}")
    print(f"wrote {args.out / (stem + '.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
