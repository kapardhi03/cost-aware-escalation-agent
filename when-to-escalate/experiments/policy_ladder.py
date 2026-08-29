"""
policy_ladder.py — the rung between a fixed action and the cost-aware policy.

`run_policies.py` reports two decision rules and three degenerate references. What
it does not contain is a policy that has the cost matrix but not the uncertainty.
This file adds that one arm and nothing else. It reads `results/run.json`, touches
no provider, and writes its own artifact, so the committed run and every claim that
rests on it are untouched.

Two things live here.

1. THE ARM. `modal_plugin` collapses the belief to its most likely joint state and
   plays the cheapest action for that state under the real matrix. It is
   certainty-equivalence: the belief enters only through its mode, and the spread
   that the expected-cost rule integrates over is discarded before any cost is
   read. The state-to-action map is DERIVED from COST by argmin, never written
   down here, so a change to the matrix moves the map with it.

2. THE IDENTITY the arm exists to sit beside. `uniform_baseline` is usually
   described by its implementation — a cost matrix with every non-zero entry
   flattened to one. Under that matrix the five expected costs have closed forms,

       EC(answer) = b_h                    EC(ask)    = 1
       EC(notify) = 1 - b_h                EC(pause)  = 1
       EC(hold)   = 1 - P(cold)(1 - b_h)

   from which the arm's whole behaviour follows without reference to any case set:
   `answer` beats `notify` exactly when b_h is below one half, which is the mode of
   the needs-human marginal rather than a threshold anyone chose; and `hold` never
   strictly wins, because EC(hold) - EC(answer) = (1 - b_h)(1 - P(cold)) >= 0. The
   agreement count against a plain threshold is already committed in
   `results/robustness.json` (`threshold_rule.uniform_baseline_vs_half_threshold`)
   and is not restated here. What this file adds is the residual between those
   closed forms and `expected_cost`, which is what makes the algebra an executed
   assertion rather than a remark.

Why the run cannot discover anything, stated up front. Every belief is committed
and the arm is a deterministic function of them, so the measured numbers are fixed
before the code runs. The comparison against the pre-registration below therefore
verifies that the implementation matches the specification; it is not evidence for
anything. A mismatch would mean the spec is wrong. This is the opposite of a sweep,
where an exact hit on a predicted boundary would warrant suspicion.

Usage
    python experiments/policy_ladder.py
    python experiments/policy_ladder.py --json results/policy-ladder.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.costs import (ACTIONS, COST, READINESS_LABELS,            # noqa: E402
                       UNIFORM_COST, State, expected_cost,
                       feasible_actions, tie_break_order)

RUN_JSON = ROOT / "results" / "run.json"

#: Pre-registered before the arm was implemented, from the committed beliefs by
#: hand. Stated here so the comparison is against a fixed target rather than
#: against whatever the code happens to produce. NOT a result and never cited as
#: one: the reportable numbers are the measured ones below.
PREREGISTRATION = {
    "mean_cost": 2.18,
    "missed_escalations": 25,
    "escalation_precision": 0.739,
    "escalation_recall": 0.405,
    "escalations": 23,
    "action_counts": {"answer": 57, "hold": 19, "escalate_notify": 23, "ask": 1},
    "map": {
        "hot|False": "answer", "warm|False": "answer", "cold|False": "hold",
        "hot|True": "escalate_notify", "warm|True": "escalate_notify",
        "cold|True": "escalate_notify",
    },
}


# --------------------------------------------------------------------------- #
# The arm
# --------------------------------------------------------------------------- #

def modal_state_map(matrix: dict | None = None) -> dict[str, str]:
    """The cheapest action in each state's column, by argmin over the matrix.

    Derived rather than written: this is the whole content of the plug-in policy,
    and authoring it by hand would make it a set of preferences I chose instead of
    a consequence of the practitioner's costs. Ties resolve safest-first, the same
    rule the expected-cost policy uses, so `(cold, False)` — where answering and
    holding both cost nothing — resolves to `hold` rather than to `answer`.
    """
    matrix = matrix if matrix is not None else COST
    rank = {a: i for i, a in enumerate(tie_break_order(matrix))}
    return {
        f"{readiness}|{needs_human}": min(
            ACTIONS, key=lambda a: (matrix[a][(readiness, needs_human)], rank[a]))
        for readiness in READINESS_LABELS
        for needs_human in (False, True)
    }


def modal_state(row: dict) -> tuple[str, bool]:
    """The most likely joint state under the belief.

    The two parts are independent by design, so the joint mode is the pair of
    marginal modes and no joint has to be formed. Readiness ties resolve in
    READINESS_LABELS order; the needs-human mode is a comparison against one half,
    which is the argmax of a two-outcome marginal and not a tuned threshold.
    """
    readiness = max(READINESS_LABELS, key=lambda r: row["belief"]["readiness"][r])
    return readiness, row["belief"]["needs_human"] > 0.5


<<<<<<< HEAD
def modal_plugin_action(row: dict, matrix: dict | None = None,
                        legacy_tie_break: bool = False) -> str:
=======
def modal_plugin_action(row: dict, matrix: dict | None = None) -> str:
>>>>>>> 93acc2c (Add the modal-state plug-in arm and execute the uniform-baseline identity)
    """Cheapest feasible action for the modal state.

    The hard constraint is applied by removing actions before the argmin, exactly
    as `choose_action` does, so a forbidden action cannot be bought back by being
    cheap in the modal column.
    """
    matrix = matrix if matrix is not None else COST
    readiness, needs_human = modal_state(row)
    rank = {a: i for i, a in enumerate(tie_break_order(matrix))}
    available = feasible_actions(row.get("constraints", ()))
    return min(available,
               key=lambda a: (matrix[a][(readiness, needs_human)], rank[a]))


# --------------------------------------------------------------------------- #
# Scoring — identical definitions to run_policies.summarise
# --------------------------------------------------------------------------- #

def realised_cost(action: str, labels: dict) -> float:
    """What the action actually cost, under the real matrix and the true state."""
    return COST[action][(labels["readiness"], labels["needs_human"])]


def score(actions: list[str], rows: list[dict]) -> dict:
    """Total, mean, misses, escalation precision and recall.

    Deliberately the same arithmetic as `run_policies.summarise`, so this arm's row
    is comparable to the committed ones rather than merely adjacent to them. An
    escalation is either escalate action, as there.
    """
    seen = [realised_cost(a, r["labels"]) for a, r in zip(actions, rows)]
    esc = [a.startswith("escalate") for a in actions]
    truth = [r["labels"]["needs_human"] for r in rows]

    tp = sum(1 for e, t in zip(esc, truth) if e and t)
    fp = sum(1 for e, t in zip(esc, truth) if e and not t)
    fn = sum(1 for e, t in zip(esc, truth) if not e and t)

    return {
        "n": len(rows),
        "total_cost": round(sum(seen), 2),
        "mean_cost": round(sum(seen) / len(rows), 4),
        "action_counts": dict(sorted(Counter(actions).items())),
        "escalations": tp + fp,
        "missed_escalations": fn,
        "escalation_precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "escalation_recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
        "constraint_violations": sum(
            1 for a, r in zip(actions, rows) if r["constraints"] and a == "answer"),
    }


# --------------------------------------------------------------------------- #
# The identity, as executed assertions rather than prose
# --------------------------------------------------------------------------- #

class _Belief:
    """The two fields `expected_cost` reads, rebuilt from a committed row."""

    def __init__(self, readiness: dict, needs_human: float) -> None:
        self.readiness = readiness
        self.needs_human = needs_human


def check_uniform_identity(rows: list[dict]) -> dict:
    """The closed forms above, against `expected_cost` on every committed belief.

    This is what turns three lines of algebra into a check. The residual is the
    largest absolute disagreement over all 100 beliefs and all five actions; the
    two inequalities are the reason the arm reduces to its mode. The agreement
    count against a plain threshold is committed in results/robustness.json and is
    deliberately not recomputed here — a second copy of a number is a second place
    for it to drift.
    """
    residual = 0.0
    hold_slack_min = None
    hold_strictly_wins = 0
    on_boundary = []

    for row in rows:
        b = _Belief(row["belief"]["readiness"], row["belief"]["needs_human"])
        b_h, cold = b.needs_human, b.readiness["cold"]
        closed = {
            "answer": b_h,
            "ask": 1.0,
            "hold": 1.0 - cold * (1.0 - b_h),
            "escalate_notify": 1.0 - b_h,
            "escalate_pause": 1.0,
        }
        for action, value in closed.items():
            residual = max(
                residual, abs(value - expected_cost(action, b, UNIFORM_COST)))

        slack = closed["hold"] - closed["answer"]
        hold_slack_min = slack if hold_slack_min is None else min(hold_slack_min, slack)
        if slack < 0:
            hold_strictly_wins += 1
        if b_h == 0.5:
            on_boundary.append(row["case_id"])

    return {
        "closed_form_max_residual": residual,
        "hold_minus_answer_min_slack": hold_slack_min,
        "cases_where_hold_strictly_beats_answer": hold_strictly_wins,
        "cases_on_the_mode_boundary": on_boundary,
        "agreement_count_source":
            "results/robustness.json threshold_rule."
            "uniform_baseline_vs_half_threshold",
    }


# --------------------------------------------------------------------------- #
# Pre-registration comparison
# --------------------------------------------------------------------------- #

def compare_to_preregistration(measured: dict, derived_map: dict) -> dict:
    """Measured against pre-registered, field by field, with the deltas kept.

    Equality is the expected outcome and is not evidence: the arm is a
    deterministic function of committed beliefs, so this compares the
    implementation against the specification and nothing else.
    """
    checks = {}
    for key in ("mean_cost", "missed_escalations", "escalations",
                "escalation_precision", "escalation_recall"):
        want, got = PREREGISTRATION[key], measured[key]
        checks[key] = {
            "predicted": want, "measured": got,
            "delta": round(got - want, 6),
            "match": abs(got - want) <= 5e-4,
        }
    checks["action_counts"] = {
        "predicted": PREREGISTRATION["action_counts"],
        "measured": measured["action_counts"],
        "match": (dict(sorted(PREREGISTRATION["action_counts"].items()))
                  == dict(sorted(measured["action_counts"].items()))),
    }
    checks["map"] = {
        "predicted": PREREGISTRATION["map"], "measured": derived_map,
        "match": PREREGISTRATION["map"] == derived_map,
    }
    return {"checks": checks,
            "all_match": all(c["match"] for c in checks.values())}


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

def render(f: dict) -> str:
    L = ["# The modal-state plug-in arm", "",
         f"Generated {f['generated_at']} · read from `{f['source']}` · "
         f"{f['n_cases']} cases · offline, no provider call.", "",
         "The belief enters only through its mode. The spread that the",
         "expected-cost rule integrates over is discarded before any cost is read,",
         "which is the one thing that separates this arm from `cost_aware`.", ""]

    L += ["## The state-to-action map, derived from the matrix", "",
          "| state | cheapest action |", "| --- | --- |"]
    # The pipe in a state key has to be escaped even inside a code span: GFM
    # splits table cells on `|` first and reads inline code afterwards, so an
    # unescaped `hot|False` renders as two columns.
    L += [f"| `{k.replace('|', chr(92) + '|')}` | `{v}` |"
          for k, v in f["map"].items()]
    L += ["", "Not authored here: the entries are `argmin` over each column of",
          "`src.costs.COST`, with ties resolved safest-first by the same",
          "`tie_break_order` the expected-cost policy uses. `cold|False` is the one",
          "tie — answering and holding both cost nothing — and it resolves to",
          "`hold`.", ""]

    L += ["## Measured", "",
          "| split | total | mean | escalations | missed | precision | recall |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for split in ("all", "dev", "test"):
        s = f["summaries"][split]
        L.append(f"| {split} | {s['total_cost']} | {s['mean_cost']} | "
                 f"{s['escalations']} | {s['missed_escalations']} | "
                 f"{s['escalation_precision']} | {s['escalation_recall']} |")
    L += ["", f"Action counts over all cases: "
              f"{f['summaries']['all']['action_counts']}.",
          f"Hard-constraint violations: "
          f"{f['summaries']['all']['constraint_violations']}.", ""]

    c = f["preregistration_comparison"]
    L += ["## Pre-registered against measured", "",
          "| field | pre-registered | measured | match |",
          "| --- | ---: | ---: | --- |"]
    for key in ("mean_cost", "escalations", "missed_escalations",
                "escalation_precision", "escalation_recall"):
        k = c["checks"][key]
        L.append(f"| {key} | {k['predicted']} | {k['measured']} | "
                 f"{'yes' if k['match'] else '**NO**'} |")
    for key in ("action_counts", "map"):
        k = c["checks"][key]
        L.append(f"| {key} | (as pre-registered) | (as measured) | "
                 f"{'yes' if k['match'] else '**NO**'} |")
    L += ["", "**What this comparison is worth.** The arm is a deterministic",
          "function of the committed beliefs, so agreement here confirms the",
          "implementation matches the specification and establishes nothing about",
          "the world. A mismatch would mean the specification is wrong. This is the",
          "reverse of a boundary sweep, where an exact hit on a predicted value",
          "would be the suspicious outcome; here it is the required one.", "",
          "The pre-registered column was computed by hand from `results/run.json`",
          "before the arm was implemented. It is not a result and is not cited as",
          "one anywhere.", ""]

    i = f["uniform_identity"]
    L += ["## Why the no-cost rung was already occupied", "",
          "Flattening every non-zero cost to one does not produce a weaker cost",
          "model; it produces no cost model at all. The five expected costs become",
          "", "```", "EC(answer) = b_h              EC(ask)   = 1",
          "EC(notify) = 1 - b_h          EC(pause) = 1",
          "EC(hold)   = 1 - P(cold)(1 - b_h)", "```", "",
          "so `answer` beats `notify` exactly where `b_h` falls below one half ---",
          "the mode of the needs-human marginal, not a threshold anyone selected ---",
          "and `hold` cannot strictly win, since",
          "`EC(hold) - EC(answer) = (1 - b_h)(1 - P(cold))`, which is never",
          "negative. `ask` and `pause` sit at 1 and are unreachable.", "",
          f"- Largest disagreement between those closed forms and",
          f"  `costs.expected_cost` over every committed belief and all five",
          f"  actions: `{i['closed_form_max_residual']}`.",
          f"- Smallest `EC(hold) - EC(answer)` over the same beliefs: "
          f"`{i['hold_minus_answer_min_slack']}`; cases where `hold` strictly wins: "
          f"{i['cases_where_hold_strictly_beats_answer']}.",
          f"- Beliefs sitting exactly on the mode boundary, where the rule's",
          f"  behaviour would be a convention rather than a consequence: "
          f"{len(i['cases_on_the_mode_boundary'])}.", "",
          "The agreement count against a plain threshold is already committed, in",
          f"`{i['agreement_count_source']}`, and is not repeated here. What is new",
          "is that the agreement is not a property of these cases: the algebra holds",
          "at every belief, so no case set could have shown otherwise.", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path,
                    default=ROOT / "results" / "policy-ladder.json")
    ap.add_argument("--md", type=Path,
                    default=ROOT / "results" / "policy-ladder.md")
    args = ap.parse_args()

    payload = json.loads(RUN_JSON.read_text(encoding="utf-8"))
    rows = payload["rows"]

    derived_map = modal_state_map()
    actions = [modal_plugin_action(r) for r in rows]

    summaries = {
        "all": score(actions, rows),
        "dev": score([a for a, r in zip(actions, rows) if r["split"] == "dev"],
                     [r for r in rows if r["split"] == "dev"]),
        "test": score([a for a, r in zip(actions, rows) if r["split"] == "test"],
                      [r for r in rows if r["split"] == "test"]),
    }

    findings = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "results/run.json",
        "n_cases": len(rows),
        "arm": "modal_plugin",
        "map": derived_map,
        "preregistration": PREREGISTRATION,
        "preregistration_comparison": compare_to_preregistration(
            summaries["all"], derived_map),
        "uniform_identity": check_uniform_identity(rows),
        "summaries": summaries,
        "decisions": [
            {"case_id": r["case_id"], "split": r["split"],
             "modal_state": "|".join(map(str, modal_state(r))),
             "action": a,
             "realised_cost": realised_cost(a, r["labels"]),
             "cost_aware_action": r["decisions"]["cost_aware"]["action"],
             "uniform_baseline_action": r["decisions"]["uniform_baseline"]["action"]}
            for a, r in zip(actions, rows)
        ],
    }

    report = render(findings)
    args.json.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")
    args.md.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"wrote {args.json}")
    print(f"wrote {args.md}")

    if not findings["preregistration_comparison"]["all_match"]:
        print("\nSTOP: measured output diverges from the pre-registration. The "
              "specification is what to re-examine, not the numbers.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

