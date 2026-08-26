"""
Guards on `experiments/abstention.py`.

Two things carry most of the weight here.

The first is byte-reproduction of the two committed artifacts. The numbers in
`results/abstention.json` are what the Gate 4 abstention call is made on, so the
risk this file exists to catch is not a wrong new number — it is a silently changed
old one.

The second is the float-noise regression. `H(b)` values that are mathematically
equal can differ in the last bit of the entropy sum, and before quantisation the
decile grid read two identical thresholds as different ones: the 10th and 20th
percentile on the published arm are both 1.62577524303632, and they fired on 49 and
44 test cases. `test_equal_tau_give_equal_rows` locks that shut, and asserts the
published arm still contains a repeated tau so the check cannot go vacuous.

Nothing here asserts which variant wins. The pre-commitment is to report whichever
outcome arrives, so the tests check that the reported summary flags agree with the
per-threshold rows they summarise, not that they point a particular way.
"""

from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import re
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "abstention.py"
COMMITTED_JSON = ROOT / "results" / "abstention.json"
COMMITTED_MD = ROOT / "results" / "abstention.md"
REBASELINE = ROOT / "results" / "rebaseline.json"
ANSWER_MODEL_JSON = ROOT / "results" / "answer-model.json"
PREREG = ROOT / "decisions" / "v2-gate4-preregistration.md"


@pytest.fixture(scope="module")
def ab():
    spec = importlib.util.spec_from_file_location("abstention", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report(ab):
    return ab.build_report()


@pytest.fixture(scope="module")
def committed():
    return json.loads(COMMITTED_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rebaseline():
    return json.loads(REBASELINE.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# The guard: the committed artifacts still come out of the code
# --------------------------------------------------------------------------- #

def test_json_reproduces_byte_for_byte(ab, report):
    fresh = json.dumps(report, indent=2, default=str)
    assert fresh == COMMITTED_JSON.read_text(encoding="utf-8")


def test_md_reproduces_byte_for_byte(ab, report):
    assert ab.render(report) == COMMITTED_MD.read_text(encoding="utf-8")


def test_no_timestamp_anywhere(ab, report):
    blob = json.dumps(report, default=str) + ab.render(report)
    assert "generated_at" not in blob
    assert not re.search(r"20\d\d-\d\d-\d\dT", blob)


def test_two_builds_agree(ab, report):
    again = ab.build_report()
    assert json.dumps(again, sort_keys=True, default=str) == \
        json.dumps(report, sort_keys=True, default=str)


def test_render_is_called_once_per_run(ab):
    """`main` must compute the text once, or stdout and the file could diverge."""
    src = inspect.getsource(ab.main)
    assert src.count("render(report)") == 1


def test_the_script_calls_no_provider(ab):
    src = SCRIPT.read_text(encoding="utf-8").lower()
    for word in ("openai", "anthropic", "requests.post", "http://", "https://",
                 "api_key", "urllib.request"):
        assert word not in src, f"{word} appears in a script that must be offline"


# --------------------------------------------------------------------------- #
# Section 1: the cost matrix, before any belief
# --------------------------------------------------------------------------- #

def test_pause_costs_strictly_more_than_notify_in_every_state(ab, report):
    m = report["matrix_facts"]
    assert m["pause_costs_strictly_more_than_notify_in_every_state"] is True
    assert len(m["by_state"]) == 6
    for row in m["by_state"]:
        assert Fraction(row["pause_minus_notify"]) > 0


def test_the_pause_penalty_bounds_are_exact(ab, report):
    m = report["matrix_facts"]
    assert m["smallest_pause_penalty"] == "1"
    assert m["largest_pause_penalty"] == "3"


def test_matrix_facts_are_read_from_the_matrix_not_typed_in(ab, report):
    for row in report["matrix_facts"]["by_state"]:
        state = (row["readiness"], row["needs_human"])
        for action in ("escalate_pause", "escalate_notify", "answer"):
            assert Fraction(row[action]) == \
                Fraction(ab.costs.COST[action][state]).limit_denominator()


def test_a_matrix_where_pause_is_cheaper_is_refused(ab):
    """Negative control: the aggregate deltas are only readable while pause is
    dominated, so the script must stop rather than report them if it is not."""
    original = copy.deepcopy(ab.costs.COST)
    try:
        ab.costs.COST["escalate_pause"][("hot", False)] = 0
        with pytest.raises(ab.AbstentionError, match="not strictly costlier"):
            ab.matrix_facts()
    finally:
        ab.costs.COST.clear()
        ab.costs.COST.update(original)


def test_escalate_pause_is_feasible_on_every_case(ab):
    """The override never has to be skipped, so there is no silent subset."""
    for forbidden in ab.costs.CONSTRAINT_FORBIDS.values():
        assert "escalate_pause" not in forbidden


# --------------------------------------------------------------------------- #
# Section 2: H(b), the quantisation, and the pre-registered grid
# --------------------------------------------------------------------------- #

def test_h_agrees_with_the_committed_answer_model_column(ab, report):
    ha = report["arms"]["published"]["h_agreement_with_committed_column"]
    assert ha["n_compared"] == 100
    assert ha["max_abs_delta"] <= ab.EXACT
    committed = {c["case_id"]: c["h_joint"]
                 for c in json.loads(ANSWER_MODEL_JSON.read_text())
                 ["per_case"]["cases"]}
    rows, _ = ab.vc.load_arm("published")
    for row in rows:
        assert abs(ab.h_of(row) - committed[row["case_id"]]) <= ab.EXACT


def test_a_disagreeing_h_column_is_refused(ab, monkeypatch):
    """Negative control on the agreement check."""
    rows, _ = ab.vc.load_arm("published")
    bad = list(rows)
    bad[0] = {**rows[0], "belief": {**rows[0]["belief"], "needs_human": 0.5}}
    with pytest.raises(ab.AbstentionError, match="disagrees with the committed"):
        ab.committed_h_agreement(bad)


def test_the_published_grid_reproduces_the_preregistered_deciles(ab, report):
    """Parsed out of the locked document, not typed into this test."""
    line = next(ln for ln in PREREG.read_text(encoding="utf-8").splitlines()
                if "deciles, 0% to 100%" in ln)
    locked = [float(x) for x in line.split("|")[2].split(",")]
    assert len(locked) == 11
    grid = report["arms"]["published"]["tau_grid"]["grid"]
    assert [round(g["tau_bits_full"], 3) for g in grid] == locked


def test_the_grid_is_eleven_deciles_on_every_arm(ab, report):
    assert ab.QUANTILES == tuple(i / 10 for i in range(11))
    for arm in ab.ARMS:
        g = report["arms"][arm]["tau_grid"]
        assert [r["quantile"] for r in g["grid"]] == list(ab.QUANTILES)
        assert g["n_in_population"] == 100
        assert g["population"] == ab.GRID_POPULATION


def test_quantisation_absorbs_noise_and_preserves_signal(ab, report):
    for arm in ab.ARMS:
        f = report["arms"][arm]["float_noise"]
        assert f["h_decimals"] == ab.H_DECIMALS
        # The tolerance has to sit strictly between the two derived bounds.
        assert f["tolerance"] > f["float_noise_bound"]
        assert f["tolerance"] < f["smallest_gap_preserved"]
        if f["largest_gap_absorbed"] is not None:
            assert f["largest_gap_absorbed"] < f["float_noise_bound"]
        assert f["margin_below_signal"] > 1e3
        assert f["margin_above_noise"] > 1e2


def test_the_published_arm_has_exactly_five_spurious_distinctions(ab, report):
    f = report["arms"]["published"]["float_noise"]
    assert f["n_distinct_before_quantising"] == 24
    assert f["n_distinct_after_quantising"] == 19
    assert f["n_spurious_distinctions_removed"] == 5
    assert f["n_gaps_below_the_noise_bound"] == 5


def test_a_tolerance_that_crosses_the_signal_is_refused(ab, monkeypatch):
    """Negative control: rounding must not be allowed to merge real values."""
    rows, _ = ab.vc.load_arm("calibrated")
    monkeypatch.setattr(ab, "H_DECIMALS", 2)
    with pytest.raises(ab.AbstentionError, match="not below the smallest genuine"):
        ab.float_noise(rows)


def test_a_tolerance_below_the_noise_bound_is_refused(ab, monkeypatch):
    """Negative control on the other end: too tight to absorb what it exists for."""
    rows, _ = ab.vc.load_arm("published")
    monkeypatch.setattr(ab, "H_DECIMALS", 17)
    with pytest.raises(ab.AbstentionError, match="not above the float noise bound"):
        ab.float_noise(rows)


def test_equal_tau_give_equal_rows(ab, report):
    """The regression this quantisation exists for.

    Two grid points with the same threshold must produce the same firing set, the
    same cost and the same misses. Before quantisation they did not, because the two
    thresholds differed by 2 ulp.
    """
    seen_a_repeat = False
    for arm in ab.ARMS:
        arm_rep = report["arms"][arm]
        by_tau: dict = {}
        for row in arm_rep["variants"]["a_threshold_override"][
                "test_claim_split"]["per_tau"]:
            tau = arm_rep["tau_grid"]["grid"][
                [r["quantile"] for r in arm_rep["tau_grid"]["grid"]]
                .index(row["quantile"])]["tau_bits_full"]
            by_tau.setdefault(tau, []).append(row)
        for tau, group in by_tau.items():
            if len(group) > 1:
                seen_a_repeat = True
            first = group[0]
            for other in group[1:]:
                for field in ("n_firing", "total_cost", "missed_escalations",
                              "n_actions_changed", "action_counts"):
                    assert other[field] == first[field], (
                        f"{arm} tau={tau} disagrees on {field}")
    assert seen_a_repeat, ("no repeated tau anywhere, so this test proved nothing; "
                           "the published arm's tied H(b) values should produce one")


# --------------------------------------------------------------------------- #
# Section 3: the baseline against the committed artifact
# --------------------------------------------------------------------------- #

def test_every_arm_reproduces_its_committed_test_split_score(ab, report, rebaseline):
    for arm in ab.ARMS:
        top, key = ab.COMMITTED_BASELINE[arm]
        ref = rebaseline[top][key]
        base = report["arms"][arm]["baseline"]
        assert base["reproduces_committed_test_split"] is True
        t = base["test_claim_split"]
        for field in ("total_cost", "mean_cost", "missed_escalations",
                      "action_counts"):
            if field in ref:
                assert t[field] == ref[field], f"{arm}.{field}"


def test_a_disagreeing_committed_score_is_refused(ab):
    """Negative control: the comparison has to be able to fail."""
    rows, _ = ab.vc.load_arm("raw")
    decisions = ab.decisions_for(rows, legacy_tie_break=False)
    bad = {"n": 50, "total_cost": 999, "mean_cost": 19.98,
           "missed_escalations": 7,
           "action_counts": {"answer": 12, "escalate_notify": 21, "hold": 17}}
    with pytest.raises(ab.AbstentionError, match="does not reproduce the committed"):
        ab.baseline_report(decisions, bad)


def test_both_splits_and_all_100_are_reported(ab, report):
    for arm in ab.ARMS:
        base = report["arms"][arm]["baseline"]
        assert base["test_claim_split"]["n"] == 50
        assert base["dev_in_sample"]["n"] == 50
        assert base["all_100"]["n"] == 100
        assert base["all_100"]["total_cost"] == pytest.approx(
            base["test_claim_split"]["total_cost"]
            + base["dev_in_sample"]["total_cost"])


def test_the_tie_break_does_not_matter_on_the_test_split_on_any_arm(ab, report):
    """The claim split is the one rebaseline.json commits, so it is the one that
    has to be insensitive. dev is not, and the difference is recorded below."""
    for arm in ab.ARMS:
        tb = report["arms"][arm]["tie_break_sensitivity"]
        assert tb["test_claim_split"]["matters"] is False
        assert tb["test_claim_split"]["n_actions_differing"] == 0


def test_the_one_dev_case_where_the_tie_break_matters_is_recorded(ab, report):
    """published dev has exactly one case that turns on the rule; this artifact
    reports the fresh (safest-first) action there, run.json reports the legacy one."""
    tb = report["arms"]["published"]["tie_break_sensitivity"]
    assert tb["dev_in_sample"]["n_actions_differing"] == 1
    case = tb["dev_in_sample"]["cases"][0]
    assert case["case_id"] == "a11-repeated-097"
    assert case["legacy"] == "answer"
    assert case["fresh"] == "hold"
    assert tb["all_100"]["cases"] == tb["dev_in_sample"]["cases"]


def test_the_baseline_never_chooses_escalate_pause(ab, report):
    """Which is why variant (a)'s changed count equals its firing count."""
    for arm in ab.ARMS:
        counts = report["arms"][arm]["baseline"]["all_100"]["action_counts"]
        assert "escalate_pause" not in counts


# --------------------------------------------------------------------------- #
# Section 4: variant (b)
# --------------------------------------------------------------------------- #

def test_b_never_changes_the_miss_count(ab, report):
    for arm in ab.ARMS:
        v = report["arms"][arm]["variants"]["b_fallback_ordering"]
        for label in ("test_claim_split", "dev_in_sample", "all_100"):
            assert v[label]["delta_missed_escalations_vs_baseline"] == 0


def test_b_scope_is_exactly_the_notify_count(ab, report):
    for arm in ab.ARMS:
        base = report["arms"][arm]["baseline"]
        v = report["arms"][arm]["variants"]["b_fallback_ordering"]
        for label in ("test_claim_split", "dev_in_sample", "all_100"):
            notify = base[label]["action_counts"].get("escalate_notify", 0)
            assert v[label]["n_actions_changed"] == notify
            assert v[label]["action_counts"].get("escalate_notify", 0) == 0
            assert v[label]["action_counts"].get("escalate_pause", 0) == notify


def test_b_cost_delta_equals_the_summed_pause_penalty(ab, report):
    """The delta is not just positive; it is the exact sum of per-case penalties."""
    for arm in ab.ARMS:
        rows, _ = ab.vc.load_arm(arm)
        decisions = ab.decisions_for(rows, legacy_tie_break=False)
        test = [d for d in decisions if d["split"] == "test"]
        expected = sum(d["cost_if_escalate_pause"] - d["cost_if_escalate_notify"]
                       for d in test if d["action"] == "escalate_notify")
        got = report["arms"][arm]["variants"]["b_fallback_ordering"][
            "test_claim_split"]["delta_total_cost_vs_baseline"]
        assert got == pytest.approx(expected)


def test_b_is_tau_independent(ab, report):
    for arm in ab.ARMS:
        v = report["arms"][arm]["variants"]["b_fallback_ordering"]
        assert v["tau_independent"] is True
        assert "per_tau" not in v


def test_b_leaves_answer_and_hold_alone(ab, report):
    for arm in ab.ARMS:
        base = report["arms"][arm]["baseline"]["test_claim_split"]["action_counts"]
        after = report["arms"][arm]["variants"]["b_fallback_ordering"][
            "test_claim_split"]["action_counts"]
        for action in ("answer", "hold"):
            assert after.get(action, 0) == base.get(action, 0)


# --------------------------------------------------------------------------- #
# Section 5: variant (a)
# --------------------------------------------------------------------------- #

def test_a_firing_count_is_non_increasing_in_tau(ab, report):
    for arm in ab.ARMS:
        for label in ("test_claim_split", "dev_in_sample", "all_100"):
            rows = report["arms"][arm]["variants"]["a_threshold_override"][
                label]["per_tau"]
            counts = [r["n_firing"] for r in rows]
            assert counts == sorted(counts, reverse=True), f"{arm}.{label}"


def test_a_misses_are_non_increasing_as_more_cases_fire(ab, report):
    """More pauses can only remove misses, never add them."""
    for arm in ab.ARMS:
        rows = report["arms"][arm]["variants"]["a_threshold_override"][
            "test_claim_split"]["per_tau"]
        for r in rows:
            assert r["delta_missed_escalations_vs_baseline"] <= 0


def test_a_changed_count_equals_firing_count(ab, report):
    for arm in ab.ARMS:
        for label in ("test_claim_split", "dev_in_sample", "all_100"):
            for r in report["arms"][arm]["variants"]["a_threshold_override"][
                    label]["per_tau"]:
                assert r["n_actions_changed"] == r["n_firing"]


def test_a_action_counts_account_for_every_case(ab, report):
    for arm in ab.ARMS:
        for label, n in (("test_claim_split", 50), ("dev_in_sample", 50),
                         ("all_100", 100)):
            for r in report["arms"][arm]["variants"]["a_threshold_override"][
                    label]["per_tau"]:
                assert sum(r["action_counts"].values()) == n
                assert r["action_counts"].get("escalate_pause", 0) == r["n_firing"]


def test_a_summary_flag_agrees_with_its_own_rows(ab, report):
    """The direction is not asserted — only that the summary matches the table.

    The pre-commitment is to report whichever way this falls, so locking the
    direction in a test would be locking in an outcome.
    """
    for arm in ab.ARMS:
        for label in ("test_claim_split", "dev_in_sample", "all_100"):
            v = report["arms"][arm]["variants"]["a_threshold_override"][label]
            beats = [r["quantile"] for r in v["per_tau"]
                     if r["delta_total_cost_vs_baseline"] < 0]
            assert v["quantiles_that_beat_baseline"] == beats
            assert v["beats_baseline_at_any_tau"] is bool(beats)
            cheapest = min(r["total_cost"] for r in v["per_tau"])
            assert v["cheapest_tau_on_this_split"]["total_cost"] == cheapest


def test_a_cost_per_miss_avoided_is_present_exactly_when_misses_fall(ab, report):
    for arm in ab.ARMS:
        for r in report["arms"][arm]["variants"]["a_threshold_override"][
                "test_claim_split"]["per_tau"]:
            fell = r["delta_missed_escalations_vs_baseline"] < 0
            assert (r["cost_per_miss_avoided"] is not None) is fell
            if fell:
                # The artifact rounds to 2dp, so compare against the same rounding
                # rather than an approx window that straddles the half-cent.
                assert r["cost_per_miss_avoided"] == round(
                    r["delta_total_cost_vs_baseline"]
                    / -r["delta_missed_escalations_vs_baseline"], 2)


# --------------------------------------------------------------------------- #
# Section 6: variant (c)
# --------------------------------------------------------------------------- #

def test_c_costs_exactly_the_baseline_at_every_tau(ab, report):
    for arm in ab.ARMS:
        for label in ("test_claim_split", "dev_in_sample", "all_100"):
            base = report["arms"][arm]["baseline"][label]
            v = report["arms"][arm]["variants"]["c_diagnostic"][label]
            assert v["total_cost"] == base["total_cost"]
            assert v["missed_escalations"] == base["missed_escalations"]
            assert v["action_counts"] == base["action_counts"]
            for r in v["per_tau"]:
                assert r["delta_total_cost_vs_baseline"] == 0
                assert r["delta_missed_escalations_vs_baseline"] == 0
                assert r["total_cost"] == base["total_cost"]


def test_c_flag_counts_match_variant_a_firing_counts(ab, report):
    """(c) reports the set (a) would act on, so the counts have to line up."""
    for arm in ab.ARMS:
        c_rows = report["arms"][arm]["variants"]["c_diagnostic"][
            "test_claim_split"]["per_tau"]
        a_rows = report["arms"][arm]["variants"]["a_threshold_override"][
            "test_claim_split"]["per_tau"]
        assert [r["n_flagged"] for r in c_rows] == [r["n_firing"] for r in a_rows]


def test_c_subcounts_never_exceed_the_flagged_count(ab, report):
    for arm in ab.ARMS:
        for r in report["arms"][arm]["variants"]["c_diagnostic"][
                "test_claim_split"]["per_tau"]:
            assert r["n_flagged_that_need_a_human"] <= r["n_flagged"]
            assert r["n_flagged_the_baseline_already_escalates"] <= r["n_flagged"]


def test_c_diverging_from_the_baseline_is_refused(ab):
    """Negative control on the identity (c) is defined by."""
    rows, _ = ab.vc.load_arm("raw")
    decisions = ab.decisions_for(rows, legacy_tie_break=False)
    grid = ab.tau_grid(rows)
    fake = {"test_claim_split": {"total_cost": 999}}
    with pytest.raises(ab.AbstentionError, match="diverged from the baseline"):
        ab.variant_c(decisions, grid, fake)


# --------------------------------------------------------------------------- #
# Section 7: the resolution counterfactual
# --------------------------------------------------------------------------- #

def test_the_case_table_is_sorted_by_h_descending(ab, report):
    for arm in ab.ARMS:
        h = [c["h_bits"] for c in
             report["arms"][arm]["resolution_counterfactual"]["cases"]]
        assert h == sorted(h, reverse=True)
        assert len(h) == 50


def test_firing_sets_nest_so_one_table_serves_every_tau(ab, report):
    for arm in ab.ARMS:
        rows = report["arms"][arm]["resolution_counterfactual"]["per_tau_aggregate"]
        counts = [r["n_firing"] for r in rows]
        assert counts == sorted(counts, reverse=True)


def test_the_answer_infeasible_count_is_the_test_split_count_not_all_100(ab, report):
    """8 cases carry no_direct_answer across all 100; 4 of them are test cases.
    The section-7 tables are test-split, so the prose has to quote 4."""
    for arm in ab.ARMS:
        rc = report["arms"][arm]["resolution_counterfactual"]
        assert rc["n_answer_infeasible_on_this_split"] == 4
        assert sum(1 for c in rc["cases"] if not c["answer_feasible"]) == 4
        assert rc["per_tau_aggregate"][0][
            "n_excluded_from_the_three_way_as_answer_infeasible"] == 4


def test_pause_costs_more_than_notify_on_every_firing_set(ab, report):
    for arm in ab.ARMS:
        for r in report["arms"][arm]["resolution_counterfactual"][
                "per_tau_aggregate"]:
            if r["n_firing"]:
                assert r["sum_cost_if_all_resolved_to_escalate_pause"] > \
                    r["sum_cost_if_all_resolved_to_escalate_notify"]


def test_the_three_way_comparison_is_on_one_case_set(ab, report):
    for arm in ab.ARMS:
        for r in report["arms"][arm]["resolution_counterfactual"][
                "per_tau_aggregate"]:
            assert r["n_answer_feasible"] + \
                r["n_excluded_from_the_three_way_as_answer_infeasible"] == \
                r["n_firing"]


def test_infeasible_answer_cases_are_the_no_direct_answer_cases(ab, report):
    for arm in ab.ARMS:
        cases = report["arms"][arm]["resolution_counterfactual"]["cases"]
        for c in cases:
            assert c["answer_feasible"] == ("no_direct_answer" not in c["constraints"])
        assert sum(1 for c in cases if not c["answer_feasible"]) == 4


def test_all_three_arms_agree_on_the_label_only_columns(ab, report):
    """Pause and notify costs depend on labels alone, so firing on all 50 test cases
    must give the same total on every arm. A cross-arm consistency check that no
    per-arm bug could pass."""
    totals = set()
    notifies = set()
    for arm in ab.ARMS:
        first = report["arms"][arm]["resolution_counterfactual"][
            "per_tau_aggregate"][0]
        assert first["n_firing"] == 50
        totals.add(first["sum_cost_if_all_resolved_to_escalate_pause"])
        notifies.add(first["sum_cost_if_all_resolved_to_escalate_notify"])
    assert len(totals) == 1, f"arms disagree on the all-pause total: {totals}"
    assert len(notifies) == 1, f"arms disagree on the all-notify total: {notifies}"


def test_per_case_counterfactual_costs_come_from_the_matrix(ab, report):
    for arm in ab.ARMS:
        for c in report["arms"][arm]["resolution_counterfactual"]["cases"]:
            state = (c["readiness_label"], c["needs_human"])
            assert c["cost_if_escalate_pause"] == \
                ab.costs.COST["escalate_pause"][state]
            assert c["cost_if_escalate_notify"] == \
                ab.costs.COST["escalate_notify"][state]
            assert c["cost_if_answer"] == ab.costs.COST["answer"][state]


# --------------------------------------------------------------------------- #
# The call stays open
# --------------------------------------------------------------------------- #

def test_the_artifact_does_not_recommend_a_variant(ab, report):
    tc = report["the_call"]
    assert tc["made_by"].startswith("Kaps")
    assert "does not recommend" in tc["what_this_script_does_not_do"]
    blob = ab.render(report).lower()
    for phrase in ("we recommend", "the right choice is", "should be adopted",
                   "therefore choose"):
        assert phrase not in blob


def test_three_arms_and_the_reason_is_recorded(ab, report):
    assert ab.ARMS == ("published", "raw", "calibrated")
    assert "rebaselined" not in report["arms"]
    assert "cache drift" in report["beliefs"]["why_three_arms_not_four"]


def test_dev_is_labelled_in_sample_everywhere_it_appears(ab, report):
    assert "in-sample" in report["beliefs"]["dev_is_in_sample"]
    for arm in ab.ARMS:
        assert "dev_in_sample" in report["arms"][arm]["baseline"]
        for variant in ("a_threshold_override", "c_diagnostic",
                        "b_fallback_ordering"):
            assert "dev_in_sample" in report["arms"][arm]["variants"][variant]


def test_no_forbidden_vocabulary(ab, report):
    blob = (json.dumps(report, default=str) + ab.render(report)
            + SCRIPT.read_text(encoding="utf-8")).lower()
    for word in ("cohort", "deliverable", "arthryx", "whatsapp", "real estate"):
        assert word not in blob
    assert not re.search(r"\bweek \d", blob)
