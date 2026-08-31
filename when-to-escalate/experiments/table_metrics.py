"""
table_metrics.py — the three metrics the results table was missing.

Usage
    python experiments/table_metrics.py

Reads results/run.json. Writes results/table-metrics.json and .md. Runs no model
and makes no decision of its own except one recomputation, described below.

WHY THIS IS A SEPARATE SCRIPT AND NOT A CHANGE TO run_policies.py
Accuracy, the information/decision cost split and the human-routing rate could all
have been added to `summarise()`. They are not, because results/run.json is
byte-compared by tests/test_make_figures.py, tests/test_voi_ceiling_arms.py and
tests/test_abstention.py, and a new key in its summaries would break the
reproduction claim those tests exist to hold. So this script reads that file and
writes its own, and the committed decisions stay the single source they were.

WHAT EACH METRIC IS

  accuracy       fraction of cases where the escalate / do-not-escalate decision
                 matches the needs-human label. Reported as a FOIL, not as an
                 objective: Section "Metrics" says accuracy would hide what the
                 design is about, and the point of putting it in the table is that
                 a reader can see it hide it.

  info cost      the part of realised cost paid by `ask`. Terminal actions
                 (answer, hold, either escalate) are decision cost. The two sum to
                 the mean cost the results table already reported, so the table
                 carries the split and not the total — printing all three would put
                 one number in two cells of one row.

  human rate     percentage of cases routed to a human, i.e. either escalate
                 action. Over 100 cases this is numerically the escalation COUNT
                 the table already had, so it replaces that column rather than
                 joining it. `identities` asserts the equality on every policy
                 instead of trusting the coincidence.

THE ONE RECOMPUTATION. results/run.json was generated with the legacy tie-break, and
the results table's footnote claims that under the corrected default only the mean
cost moves. Three new columns make that claim wider than it was written to be, so
`corrected_tie_break` re-decides the cost-aware policy on the committed beliefs with
the corrected order and reports every column, rather than leaving the footnote to
cover ground nobody checked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from belief import Belief                                    # noqa: E402
from costs import COST, choose_action                        # noqa: E402

RUN_PATH = PROJECT_ROOT / "results" / "run.json"
OUT_JSON = PROJECT_ROOT / "results" / "table-metrics.json"
OUT_MD = PROJECT_ROOT / "results" / "table-metrics.md"

#: Policies in the results table, in the order the table lists them.
POLICIES = ("cost_aware", "uniform_baseline", "always_notify",
            "always_ask", "always_answer")

#: Actions that gather information rather than settling the case. Exactly one, and
#: naming it as a set rather than a string is what keeps the split honest if a
#: second such action is ever priced.
INFO_ACTIONS = frozenset({"ask"})

#: Written down before the script existed, and worth less than the plug-in arm's
#: pre-registration for a reason that has to be stated: these values were computed
#: by hand from the committed rows first, so a match here checks the arithmetic and
#: predicts nothing. It is a regression test with an honest label, not evidence.
PREREGISTRATION = {
    "accuracy": {"cost_aware": 0.67, "uniform_baseline": 0.70,
                 "always_notify": 0.42, "always_ask": 0.58,
                 "always_answer": 0.66},
    "info_cost": {"cost_aware": 0.0, "uniform_baseline": 0.0,
                  "always_notify": 0.0, "always_ask": 2.84,
                  "always_answer": 0.0},
    "decision_cost": {"cost_aware": 1.72, "uniform_baseline": 2.58,
                      "always_notify": 1.74, "always_ask": 0.0,
                      "always_answer": 3.40},
    "human_rate": {"cost_aware": 43, "uniform_baseline": 24,
                   "always_notify": 100, "always_ask": 0, "always_answer": 8},
    "base_rate": 0.42,
    "corrected_cost_aware_decision_cost": 1.65,
    "corrected_changes_only_decision_cost": True,
}


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

def escalates(action: str) -> bool:
    """Whether an action puts the case in front of a person.

    Both escalate actions do; `ask` does not, since it addresses the sender and
    not an operator. This is the same predicate `run_policies.summarise` uses for
    precision and recall, restated here because this script must not import a
    private helper from a module whose output it is checking.
    """
    return action.startswith("escalate")


def confusion(rows: list[dict], policy: str) -> dict:
    """The escalate / do-not-escalate confusion counts against needs_human."""
    tp = fp = fn = tn = 0
    for r in rows:
        predicted = escalates(r["decisions"][policy]["action"])
        actual = bool(r["labels"]["needs_human"])
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif actual:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def metrics(rows: list[dict], policy: str) -> dict:
    """Every column of the results table for one policy, new ones included.

    Precision, recall and the miss count are recomputed here even though
    results/run.json already reports them. That is deliberate and it is a CHECK, not
    a second copy: `agrees_with_committed` compares them against the committed
    summary, and the table keeps citing the committed file. A silent disagreement
    would mean this script and the run disagree about what an escalation is, which
    is exactly the failure the check is for.
    """
    n = len(rows)
    c = confusion(rows, policy)
    info = sum(r["decisions"][policy]["realised_cost"] for r in rows
               if r["decisions"][policy]["action"] in INFO_ACTIONS)
    total = sum(r["decisions"][policy]["realised_cost"] for r in rows)

    return {
        "n": n,
        "confusion": c,
        "accuracy": round((c["tp"] + c["tn"]) / n, 4),
        "precision": (round(c["tp"] / (c["tp"] + c["fp"]), 4)
                      if c["tp"] + c["fp"] else None),
        "recall": (round(c["tp"] / (c["tp"] + c["fn"]), 4)
                   if c["tp"] + c["fn"] else None),
        "missed_escalations": c["fn"],
        "mean_cost": round(total / n, 4),
        "mean_decision_cost": round((total - info) / n, 4),
        "mean_info_cost": round(info / n, 4),
        "human_count": c["tp"] + c["fp"],
        "human_rate_pct": round(100 * (c["tp"] + c["fp"]) / n, 2),
        "asks": sum(1 for r in rows
                    if r["decisions"][policy]["action"] in INFO_ACTIONS),
    }


def agrees_with_committed(measured: dict, committed: dict) -> dict:
    """Do the recomputed old columns match results/run.json?

    Only the three columns that already existed are compared. The new ones have
    nothing to compare against, which is the whole reason this script exists.
    """
    checks = {
        "mean_cost": (measured["mean_cost"], committed["mean_cost"]),
        "precision": (measured["precision"], committed["escalation_precision"]),
        "recall": (measured["recall"], committed["escalation_recall"]),
        "missed_escalations": (measured["missed_escalations"],
                              committed["missed_escalations"]),
    }
    out = {}
    for key, (mine, theirs) in checks.items():
        if mine is None or theirs is None:
            out[key] = mine is None and theirs is None
        else:
            out[key] = abs(mine - theirs) < 5e-4
    return out


def identities(rows: list[dict], measured: dict) -> dict:
    """Coincidences in the new column that are not coincidences.

    Two entries of the accuracy column are forced rather than measured, and a table
    that shows them without saying so invites a reader to read discrimination into
    an arithmetic identity.

    always-notify escalates on every case, so tn = fn = 0 and accuracy collapses to
    tp/n, which is both its precision and the base rate of the label. always-ask
    escalates on none, so tp = fp = 0 and accuracy collapses to tn/n, which is one
    minus the base rate — the score of the majority class. So the table already
    contains its own trivial-classifier reference point, at the always-ask row.
    """
    base = sum(1 for r in rows if r["labels"]["needs_human"]) / len(rows)
    notify, ask = measured["always_notify"], measured["always_ask"]
    return {
        "label_base_rate": round(base, 4),
        "always_notify_accuracy_equals_base_rate":
            abs(notify["accuracy"] - base) < 5e-4,
        "always_notify_accuracy_equals_its_precision":
            abs(notify["accuracy"] - notify["precision"]) < 5e-4,
        "always_ask_accuracy_equals_majority_class":
            abs(ask["accuracy"] - (1 - base)) < 5e-4,
    }


def corrected_tie_break(rows: list[dict], committed_summary: dict) -> dict:
    """The cost-aware row under the corrected tie-break, every column.

    The committed run used the legacy order and the table's footnote says only the
    mean cost differs. That was written when the row had four numbers; it now has
    seven, so the claim is re-established here rather than extended on trust.

    The decisions are re-derived from the committed beliefs with the same
    `choose_action` the run used, so this is the run's own rule at a different
    setting and not a reimplementation of it.
    """
    decided, changed = [], []
    for r in rows:
        b = Belief.from_dict(r["belief"])
        action = choose_action(b, r["constraints"], matrix=COST).action
        was = r["decisions"]["cost_aware"]["action"]
        if action != was:
            changed.append({"case_id": r["case_id"], "legacy": was,
                            "corrected": action})
        decided.append({**r, "decisions": {**r["decisions"],
                                           "cost_aware": {
                                               "action": action,
                                               "realised_cost": COST[action][(
                                                   r["labels"]["readiness"],
                                                   bool(r["labels"]["needs_human"]))],
                                           }}})

    m = metrics(decided, "cost_aware")
    legacy = metrics(rows, "cost_aware")
    moved = sorted(k for k in ("accuracy", "precision", "recall",
                               "missed_escalations", "mean_decision_cost",
                               "mean_info_cost", "human_rate_pct")
                   if m[k] != legacy[k])
    return {
        "decisions_changed": changed,
        "columns_that_move": moved,
        "only_decision_cost_moves": moved == ["mean_decision_cost"],
        "corrected": m,
        "legacy": legacy,
        "committed_mean_cost": committed_summary["mean_cost"],
    }


def human_rate_is_the_old_column(measured: dict, committed: dict) -> dict:
    """Is the human-routing rate the escalation count the table already had?

    It is, over 100 cases, and that is the point: adding a `Human %` column beside
    the old `Esc.` column would have put one number in two cells of the same row.
    The equality is asserted here so the table can REPLACE the column instead of
    joining it, and so the replacement stops being safe the moment n is not 100.
    """
    out = {}
    for p in POLICIES:
        counts = committed["policies"][p]["action_counts"]
        escalations = sum(v for k, v in counts.items() if escalates(k))
        out[p] = {
            "committed_escalation_count": escalations,
            "recomputed_human_count": measured[p]["human_count"],
            "human_rate_pct": measured[p]["human_rate_pct"],
            "count_equals_pct_because_n_is_100":
                measured[p]["n"] == 100
                and abs(measured[p]["human_rate_pct"] - escalations) < 5e-4,
            "agrees": escalations == measured[p]["human_count"],
        }
    return out


def compare(measured: dict, corrected: dict, base_rate: float) -> dict:
    """Measured against the written-down values, field by field."""
    checks = {}
    for field in ("accuracy", "info_cost", "decision_cost", "human_rate"):
        key = {"accuracy": "accuracy", "info_cost": "mean_info_cost",
               "decision_cost": "mean_decision_cost",
               "human_rate": "human_rate_pct"}[field]
        checks[field] = {
            p: abs(measured[p][key] - PREREGISTRATION[field][p]) < 5e-3
            for p in POLICIES}
    checks["base_rate"] = abs(base_rate - PREREGISTRATION["base_rate"]) < 5e-4
    checks["corrected_cost_aware_decision_cost"] = abs(
        corrected["corrected"]["mean_decision_cost"]
        - PREREGISTRATION["corrected_cost_aware_decision_cost"]) < 5e-3
    checks["corrected_changes_only_decision_cost"] = (
        corrected["only_decision_cost_moves"]
        == PREREGISTRATION["corrected_changes_only_decision_cost"])

    def flat(v):
        return all(flat(x) for x in v.values()) if isinstance(v, dict) else bool(v)

    return {"status": "arithmetic check, not a prediction — the values were "
                      "computed by hand from the committed rows first",
            "checks": checks, "all_match": all(flat(v) for v in checks.values())}


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def render(f: dict) -> str:
    m = f["metrics"]
    fmt = lambda v: "--" if v is None else f"{v}"        # noqa: E731

    L = ["# The results table, with the three columns it was missing", "",
         "Read from `results/run.json`; that file is unchanged and remains the "
         "source for every column that was already there. Accuracy, the "
         "information/decision split and the human-routing rate are computed here.",
         "",
         "| policy | accuracy | precision | recall | missed | decision cost | "
         "info cost | human % |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for p in POLICIES:
        r = m[p]
        L.append(f"| `{p}` | {r['accuracy']} | {fmt(r['precision'])} | "
                 f"{fmt(r['recall'])} | {r['missed_escalations']} | "
                 f"{r['mean_decision_cost']} | {r['mean_info_cost']} | "
                 f"{r['human_rate_pct']} |")

    i = f["identities"]
    L += ["", "## Two entries of the accuracy column are forced", "",
          f"The label base rate is **{i['label_base_rate']}**. `always_notify` "
          "escalates everywhere, so its accuracy is its precision and both are the "
          f"base rate ({i['always_notify_accuracy_equals_base_rate']}, "
          f"{i['always_notify_accuracy_equals_its_precision']}). `always_ask` "
          "escalates nowhere, so its accuracy is one minus the base rate — the "
          "majority-class score, which the table therefore already contains "
          f"({i['always_ask_accuracy_equals_majority_class']}).", "",
          "## `human %` replaces the old escalation count, it does not join it", "",
          "| policy | committed escalations | recomputed | human % | equal |",
          "| --- | ---: | ---: | ---: | :---: |"]
    for p, h in f["human_rate_check"].items():
        L.append(f"| `{p}` | {h['committed_escalation_count']} | "
                 f"{h['recomputed_human_count']} | {h['human_rate_pct']} | "
                 f"{h['count_equals_pct_because_n_is_100']} |")

    c = f["corrected_tie_break"]
    L += ["", "## The cost-aware row under the corrected tie-break", "",
          f"Decisions that change: **{len(c['decisions_changed'])}** "
          f"({', '.join(d['case_id'] for d in c['decisions_changed']) or 'none'}). "
          f"Columns that move: **{', '.join(c['columns_that_move']) or 'none'}**. "
          f"Only the decision cost moves: **{c['only_decision_cost_moves']}**, so "
          "the footnote's claim survives the three new columns.", "",
          f"legacy {c['legacy']['mean_decision_cost']} → corrected "
          f"{c['corrected']['mean_decision_cost']}", "",
          "## Old columns, recomputed against the committed run", "",
          "| policy | " + " | ".join(f["committed_agreement"][POLICIES[0]]) + " |",
          "| --- | " + " | ".join([":---:"] * 4) + " |"]
    for p in POLICIES:
        a = f["committed_agreement"][p]
        L.append(f"| `{p}` | " + " | ".join(str(a[k]) for k in a) + " |")

    cmp_ = f["preregistration_comparison"]
    L += ["", "## Pre-registration", "", f"_{cmp_['status']}._", "",
          f"All fields match: **{cmp_['all_match']}**", ""]
    return "\n".join(L)


def main() -> int:
    run = json.loads(RUN_PATH.read_text(encoding="utf-8"))
    rows, summary = run["rows"], run["summaries"]["all"]

    measured = {p: metrics(rows, p) for p in POLICIES}
    ident = identities(rows, measured)
    corrected = corrected_tie_break(rows, summary["policies"]["cost_aware"])

    findings = {
        "source": "results/run.json (unmodified)",
        "n_cases": len(rows),
        "metrics": measured,
        "identities": ident,
        "human_rate_check": human_rate_is_the_old_column(measured, summary),
        "corrected_tie_break": corrected,
        "committed_agreement": {
            p: agrees_with_committed(measured[p], summary["policies"][p])
            for p in POLICIES},
        "preregistration": PREREGISTRATION,
        "preregistration_comparison": compare(measured, corrected,
                                              ident["label_base_rate"]),
    }

    OUT_JSON.write_text(json.dumps(findings, indent=2), encoding="utf-8")
    OUT_MD.write_text(render(findings), encoding="utf-8")
    print(render(findings))
    print(f"\nwrote {OUT_JSON}\nwrote {OUT_MD}")

    status = 0
    if not findings["preregistration_comparison"]["all_match"]:
        print("\nSTOP: measured output diverges from what was written down.",
              file=sys.stderr)
        status = 1
    bad = [p for p, a in findings["committed_agreement"].items()
           if not all(a.values())]
    if bad:
        print(f"\nSTOP: recomputed columns disagree with results/run.json for "
              f"{bad}. This script and the run disagree about what an escalation "
              f"is; do not use either number until that is resolved.",
              file=sys.stderr)
        status = 1
    if not all(h["agrees"] for h in findings["human_rate_check"].values()):
        print("\nSTOP: the human-routing rate is not the committed escalation "
              "count, so it cannot replace that column.", file=sys.stderr)
        status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
