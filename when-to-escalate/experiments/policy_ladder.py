"""
policy_ladder.py — the rung between a fixed action and the cost-aware policy.

`run_policies.py` reports two decision rules and three degenerate references. What
it does not contain is a policy that has the cost matrix but not the uncertainty.
This file adds that one arm and nothing else. It reads `results/run.json`, touches
no provider, and writes its own artifact, so the committed run and every claim that
rests on it are untouched.

Three things live here.

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

3. WHERE THE ARM'S MARGIN COMES FROM, which is not where the arm was built to look.
   FOUND POST-HOC. The arm was specified, pre-registered and run before this
   section existed; the attribution below was computed afterwards, while checking
   whether the arm was comparable to a committed table generated under the other
   tie-break order. It is therefore an observation about the belief set and the
   matrix, not a confirmed prediction, and the artifact labels it as such. Nothing
   in it lends any credibility to the pre-registered check in item 1, or takes any
   away.

   What it measures: the arm under both tie-break orders, its disagreements with
   the uniform baseline split by action pair, whether the matrix expresses any
   preference at all in the column each disagreement turns on, and the realised
   points each group of swaps moves. The reason to measure it is that a rung whose
   advantage rests on a convention rather than on a cost is not the rung it appears
   to be.

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

#: Pre-registered for the attribution section before it was implemented, in the same
#: way and with the same status: a target to be compared against, never a result.
#: Note the asymmetry with PREREGISTRATION above. The arm itself was predicted before
#: anyone had looked; these values were predicted before the section was written but
#: AFTER the effect had been noticed by hand, so a match here is worth strictly less.
#: Stating them anyway is what keeps the implementation honest about the arithmetic.
ATTRIBUTION_PREREGISTRATION = {
    "legacy_mean_cost": 2.62,
    "legacy_action_counts": {"answer": 76, "ask": 1, "escalate_notify": 23},
    "legacy_missed_escalations": 25,
    "corrected_mean_cost": 2.18,
    "disagreements_vs_baseline": 20,
    "disagreement_pairs": {"hold->answer": 19, "ask->escalate_notify": 1},
    "points_saved_by_the_hold_swaps": 44,
    "points_lost_by_the_single_ask": -4,
    "net_points_vs_baseline": 40,
    "disagreements_on_an_indifferent_column": 19,
}


# --------------------------------------------------------------------------- #
# The arm
# --------------------------------------------------------------------------- #

def _rank(matrix: dict, legacy_tie_break: bool) -> dict[str, int]:
    """Tie-break ranks, mirroring `choose_action`'s two configurations exactly.

    Kept as one helper so the arm cannot drift from the policy it is compared to.
    `legacy_tie_break=True` restores ACTIONS order, which resolves indifference
    toward `answer`; it is the configuration `results/run.json` was generated in.
    """
    order = ACTIONS if legacy_tie_break else tie_break_order(matrix)
    return {a: i for i, a in enumerate(order)}


def modal_state_map(matrix: dict | None = None,
                    legacy_tie_break: bool = False) -> dict[str, str]:
    """The cheapest action in each state's column, by argmin over the matrix.

    Derived rather than written: this is the whole content of the plug-in policy,
    and authoring it by hand would make it a set of preferences I chose instead of
    a consequence of the practitioner's costs. Ties resolve safest-first, the same
    rule the expected-cost policy uses, so `(cold, False)` — where answering and
    holding both cost nothing — resolves to `hold` rather than to `answer`.

    That tie is not a detail. Under `legacy_tie_break=True` the same column resolves
    to `answer`, and the whole `hold` column of the arm disappears — which is what
    `attribute_margin` measures.
    """
    matrix = matrix if matrix is not None else COST
    rank = _rank(matrix, legacy_tie_break)
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


def modal_plugin_action(row: dict, matrix: dict | None = None,
                        legacy_tie_break: bool = False) -> str:
    """Cheapest feasible action for the modal state.

    The hard constraint is applied by removing actions before the argmin, exactly
    as `choose_action` does, so a forbidden action cannot be bought back by being
    cheap in the modal column.
    """
    matrix = matrix if matrix is not None else COST
    readiness, needs_human = modal_state(row)
    rank = _rank(matrix, legacy_tie_break)
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
    ask_corner = []

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
        # The one corner where `ask` is not ruled out: remove `answer`, and at
        # b_h = 0 with P(cold) = 0 the four remaining actions all cost 1. Every
        # UNIFORM_COST row has worst case 1, so the derived tie-break order
        # degenerates to declaration order and would resolve that tie to `ask`.
        if row.get("constraints") and b_h == 0.0 and cold == 0.0:
            ask_corner.append(row["case_id"])

    return {
        "closed_form_max_residual": residual,
        "hold_minus_answer_min_slack": hold_slack_min,
        "cases_where_hold_strictly_beats_answer": hold_strictly_wins,
        "cases_on_the_mode_boundary": on_boundary,
        "restricted_cases_at_the_ask_corner": ask_corner,
        "agreement_count_source":
            "results/robustness.json threshold_rule."
            "uniform_baseline_vs_half_threshold",
    }


# --------------------------------------------------------------------------- #
# Where the margin comes from — FOUND POST-HOC, see docstring item 3
# --------------------------------------------------------------------------- #

def attribute_margin(rows: list[dict], corrected: list[str],
                     legacy: list[str]) -> dict:
    """Split the arm's margin over the baseline into what caused each part.

    The question this answers: when the plug-in arm departs from the uniform
    baseline, does the practitioner's matrix express a PREFERENCE in the column the
    departure turns on, or is it indifferent there? An indifferent column means the
    decision came from the tie-break convention and not from any cost. That
    distinction is invisible in the mean and is the whole finding.

    The baseline's own realised costs are READ from `results/run.json` rather than
    recomputed, so this function cannot become a second authoritative copy of a
    committed number; `baseline_agrees_with_committed` asserts the recomputation
    matches, which is a check rather than a restatement.
    """
    disagreements, saved, lost, indifferent = [], 0, 0, 0
    mismatched_baseline = []

    for action, row in zip(corrected, rows):
        base = row["decisions"]["uniform_baseline"]["action"]
        committed = row["decisions"]["uniform_baseline"]["realised_cost"]
        if realised_cost(base, row["labels"]) != committed:
            mismatched_baseline.append(row["case_id"])
        if action == base:
            continue

        state = modal_state(row)
        mine, theirs = COST[action][state], COST[base][state]
        delta = committed - realised_cost(action, row["labels"])
        if mine == theirs:
            indifferent += 1
        if action == "ask":
            lost += delta
        else:
            saved += delta

        disagreements.append({
            "case_id": row["case_id"], "modal_state": "|".join(map(str, state)),
            "plugin_action": action, "baseline_action": base,
            "plugin_cost_in_modal_column": mine,
            "baseline_cost_in_modal_column": theirs,
            "matrix_is_indifferent_here": mine == theirs,
            "realised_points_saved": delta,
        })

    pairs = Counter(f"{d['plugin_action']}->{d['baseline_action']}"
                    for d in disagreements)
    moved = [d for d in disagreements
             if d["matrix_is_indifferent_here"] and d["realised_points_saved"]]
    return {
        "status": "FOUND POST-HOC — see module docstring item 3. Not a "
                  "pre-registered prediction of the arm.",
        "corrected": score(corrected, rows),
        "legacy": score(legacy, rows),
        "legacy_map": modal_state_map(legacy_tie_break=True),
        "baseline_agrees_with_committed": not mismatched_baseline,
        "baseline_recomputation_mismatches": mismatched_baseline,
        "disagreements_vs_baseline": len(disagreements),
        "disagreement_pairs": dict(sorted(pairs.items())),
        "disagreements_on_an_indifferent_column": indifferent,
        "indifferent_swaps_that_moved_realised_cost": len(moved),
        "points_saved_by_the_hold_swaps": saved,
        "points_lost_by_the_single_ask": lost,
        "net_points_vs_baseline": saved + lost,
        "disagreements": disagreements,
    }


def compare_attribution(measured: dict) -> dict:
    """Attribution against its pre-registration, same shape as the arm's.

    A match here is worth less than a match on the arm, because the effect was
    noticed by hand before these values were written down. The comparison is kept
    so the arithmetic is checked, not so the finding is credited.
    """
    got = {
        "legacy_mean_cost": measured["legacy"]["mean_cost"],
        "legacy_action_counts": measured["legacy"]["action_counts"],
        "legacy_missed_escalations": measured["legacy"]["missed_escalations"],
        "corrected_mean_cost": measured["corrected"]["mean_cost"],
        "disagreements_vs_baseline": measured["disagreements_vs_baseline"],
        "disagreement_pairs": measured["disagreement_pairs"],
        "points_saved_by_the_hold_swaps": measured["points_saved_by_the_hold_swaps"],
        "points_lost_by_the_single_ask": measured["points_lost_by_the_single_ask"],
        "net_points_vs_baseline": measured["net_points_vs_baseline"],
        "disagreements_on_an_indifferent_column":
            measured["disagreements_on_an_indifferent_column"],
    }
    checks = {}
    for key, want in ATTRIBUTION_PREREGISTRATION.items():
        have = got[key]
        if isinstance(want, dict):
            match = dict(sorted(want.items())) == dict(sorted(have.items()))
        elif isinstance(want, float):
            match = abs(have - want) <= 5e-4
        else:
            match = have == want
        checks[key] = {"predicted": want, "measured": have, "match": match}
    return {"status": "post-hoc, not a validated prediction",
            "checks": checks,
            "all_match": all(c["match"] for c in checks.values())}


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

def render_attribution(f: dict) -> list[str]:
    """The margin-attribution section. Marked post-hoc at the top, not in a footnote."""
    a = f["margin_attribution"]
    c = f["attribution_comparison"]
    esc = lambda s: s.replace("|", chr(92) + "|")          # noqa: E731

    L = ["## Where the arm's margin actually comes from", "",
         "**FOUND POST-HOC.** The arm above was specified, pre-registered and run",
         "before this section existed. This attribution was computed afterwards,",
         "while checking whether the arm was comparable to a committed table",
         "generated under the other tie-break order. It is an observation, not a",
         "confirmed prediction, and it neither supports nor undermines the",
         "pre-registered check above.", "",
         "| configuration | mean | missed | action counts |",
         "| --- | ---: | ---: | --- |",
         f"| safest-first (default) | {a['corrected']['mean_cost']} | "
         f"{a['corrected']['missed_escalations']} | "
         f"`{a['corrected']['action_counts']}` |",
         f"| legacy, ties toward `answer` | {a['legacy']['mean_cost']} | "
         f"{a['legacy']['missed_escalations']} | "
         f"`{a['legacy']['action_counts']}` |", "",
         "The `hold` column does not shrink under the legacy order; it disappears.",
         "Every one of those decisions was a tie, so every one of them moves.", ""]

    L += [f"The arm departs from the uniform baseline on "
          f"{a['disagreements_vs_baseline']} cases:", ""]
    L += [f"- `{k}` on {v} cases" for k, v in a["disagreement_pairs"].items()]
    L += ["", "| case | modal state | plug-in | baseline | cost of each, in that "
          "column | matrix indifferent? | points saved |",
          "| --- | --- | --- | --- | ---: | --- | ---: |"]
    for d in a["disagreements"]:
        L.append(f"| `{d['case_id']}` | `{esc(d['modal_state'])}` | "
                 f"`{d['plugin_action']}` | `{d['baseline_action']}` | "
                 f"{d['plugin_cost_in_modal_column']} vs "
                 f"{d['baseline_cost_in_modal_column']} | "
                 f"{'yes' if d['matrix_is_indifferent_here'] else '**no**'} | "
                 f"{d['realised_points_saved']} |")

    L += ["", f"On {a['disagreements_on_an_indifferent_column']} of the "
              f"{a['disagreements_vs_baseline']}, the two actions cost the SAME in "
              f"the column the decision turns on, so the practitioner's magnitudes "
              f"express no preference there and the tie-break convention decides. "
              f"Those swaps save {a['points_saved_by_the_hold_swaps']} realised "
              f"points. The remaining case is the one where the matrix does prefer "
              f"the arm's action at the mode, and there the arm is wrong: it costs "
              f"{-a['points_lost_by_the_single_ask']} points. Net: "
              f"{a['net_points_vs_baseline']}.", "",
          "So the rung's advantage is a convention applied to an indifference. Strip",
          "the convention and certainty-equivalence with the full matrix is worse",
          "than with the flattened one, by exactly the cost of the single decision",
          "the magnitudes genuinely drive.", "",
          f"Sharper still: only "
          f"{a['indifferent_swaps_that_moved_realised_cost']} of the "
          f"{a['disagreements_on_an_indifferent_column']} indifferent swaps change "
          f"realised cost at all. The rest hold a case that answering would also "
          f"have got right, at no gain and no loss. The whole margin therefore rests "
          f"on a handful of cases decided by a convention on a column where the "
          f"matrix says nothing.", "",
          f"Baseline realised costs are read from `results/run.json`, not recomputed "
          f"as a second copy; the recomputation was checked against the committed "
          f"field on every case and agrees: "
          f"`{a['baseline_agrees_with_committed']}`.", "",
          "| field | pre-registered | measured | match |",
          "| --- | ---: | ---: | --- |"]
    for key, k in c["checks"].items():
        pre = k["predicted"] if not isinstance(k["predicted"], dict) else "(as listed)"
        got = k["measured"] if not isinstance(k["measured"], dict) else "(as listed)"
        L.append(f"| {key} | {pre} | {got} | {'yes' if k['match'] else '**NO**'} |")
    L += ["", "These were written down before the section was implemented but after",
          "the effect had been noticed by hand, so agreement checks the arithmetic",
          "and nothing more. It is not the pre-registration the arm has.", ""]
    return L


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

    L += render_attribution(f)

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
          "negative. `ask` and `pause` both sit at 1, which the smaller of the first",
          "two is always strictly below, so on the UNCONSTRAINED menu neither is ever",
          "selected. Remove `answer` and one corner survives: at `b_h = 0` with",
          "`P(cold) = 0` the four remaining actions all cost 1, and since every",
          "`UNIFORM_COST` row has worst case 1 the derived order degenerates to",
          "declaration order and resolves that tie to `ask`.", "",
          f"- Largest disagreement between those closed forms and",
          f"  `costs.expected_cost` over every committed belief and all five",
          f"  actions: `{i['closed_form_max_residual']}`.",
          f"- Smallest `EC(hold) - EC(answer)` over the same beliefs: "
          f"`{i['hold_minus_answer_min_slack']}`; cases where `hold` strictly wins: "
          f"{i['cases_where_hold_strictly_beats_answer']}.",
          f"- Beliefs sitting exactly on the mode boundary, where the rule's",
          f"  behaviour would be a convention rather than a consequence: "
          f"{len(i['cases_on_the_mode_boundary'])}.",
          f"- Restricted cases sitting in the `ask` corner, where the conclusion",
          f"  above would not hold: "
          f"{len(i['restricted_cases_at_the_ask_corner'])}.", "",
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
    legacy_actions = [modal_plugin_action(r, legacy_tie_break=True) for r in rows]
    attribution = attribute_margin(rows, actions, legacy_actions)

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
        "attribution_preregistration": ATTRIBUTION_PREREGISTRATION,
        "attribution_comparison": compare_attribution(attribution),
        "margin_attribution": attribution,
        "uniform_identity": check_uniform_identity(rows),
        "summaries": summaries,
        "decisions": [
            {"case_id": r["case_id"], "split": r["split"],
             "modal_state": "|".join(map(str, modal_state(r))),
             "action": a,
             "legacy_tie_break_action": la,
             "realised_cost": realised_cost(a, r["labels"]),
             "cost_aware_action": r["decisions"]["cost_aware"]["action"],
             "uniform_baseline_action": r["decisions"]["uniform_baseline"]["action"]}
            for a, la, r in zip(actions, legacy_actions, rows)
        ],
    }

    report = render(findings)
    args.json.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")
    args.md.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"wrote {args.json}")
    print(f"wrote {args.md}")

    status = 0
    if not findings["preregistration_comparison"]["all_match"]:
        print("\nSTOP: measured output diverges from the pre-registration. The "
              "specification is what to re-examine, not the numbers.",
              file=sys.stderr)
        status = 1
    if not findings["attribution_comparison"]["all_match"]:
        print("\nSTOP: the margin attribution diverges from what was written down "
              "for it. Divergence here is a finding about the belief set and the "
              "matrix, not a number to nudge.", file=sys.stderr)
        status = 1
    if not findings["margin_attribution"]["baseline_agrees_with_committed"]:
        print("\nSTOP: recomputed baseline costs disagree with the committed "
              "realised_cost field in results/run.json.", file=sys.stderr)
        status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())

