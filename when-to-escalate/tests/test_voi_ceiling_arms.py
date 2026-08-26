"""
The Gate 4 belief arms, and the guard that pins Gate 1's artifact.

The load-bearing test here is
`test_the_published_arm_reproduces_the_committed_artifact`. Gate 4
adds three new belief sources to `experiments/voi_ceiling.py`, and the risk in
doing that is not a wrong new number — it is a silently changed old one. If the
refactor that introduced `--arm` shifted a key, rounded differently, or reordered
the findings dict, every Gate 4 contrast would be measured against a moved
baseline while still being described as Gate 1's. Comparing the rendered JSON
against the committed `results/voi-ceiling.json` is what makes "the arms
are a superset of Gate 1, not a revision of it" checkable.

That comparison was byte-for-byte until the grid crosscheck's float columns turned
out to depend on the CPython version. It now runs through
`tests/reproduction.py`, which forgives a float-versus-float leaf by 1e-9 and
nothing else: the `Fraction`s this file's exactness claims live in are string
leaves, and a shifted key, a changed count, a reordered dict and a changed list
length all still fail.

The other tests here assert the two pre-registered falsifiers that are properties
of the committed map rather than of any arm's decisions: that the stored knots
reproduce the stored calibrated scores, and that no calibrated score sits below the
map's floor. The floor is the constant the Gate 4 headline rests on, so it is
pinned as an exact rational rather than a float literal.

The arm-shape tests load beliefs and assert coverage. They deliberately compute no
ceiling for the three fresh arms — a loader that quietly drops three cases would
otherwise compare 97 against 100 and look fine.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

import reproduction

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "results" / "voi-ceiling.json"
COMMITTED_ARMS = ROOT / "results" / "voi-ceiling-arms.json"
COMMITTED_ARMS_MD = ROOT / "results" / "voi-ceiling-arms.md"
REBASELINE = ROOT / "results" / "rebaseline.json"

#: The three rationals the Gate 4 headline lines up. Written as Fractions so the
#: ordering claim is exact and a float literal cannot drift into the file.
POSITIVE_VOI_BOUND = Fraction(1, 5)      # constrained-menu region, all-hot ray
T_STAR = Fraction(3, 13)                 # answer vs escalate_notify crossover
ISOTONIC_FLOOR = Fraction(6, 23)         # lowest pooled PAVA block's positive rate


@pytest.fixture(scope="module")
def vc():
    """`experiments/voi_ceiling.py`, loaded by path.

    It is a script rather than a package module and puts the repo root on sys.path
    itself, so its `from src...` imports resolve.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "voi_ceiling", ROOT / "experiments" / "voi_ceiling.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def elicitation():
    return json.loads(
        (ROOT / "results" / "logprob-elicitation.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vca():
    """`experiments/voi_ceiling_arms.py`, loaded by path."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "voi_ceiling_arms", ROOT / "experiments" / "voi_ceiling_arms.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report(vca):
    """Built once — four arms at grid 60 is the expensive part of this file."""
    return vca.build_report(grid=60)


# --------------------------------------------------------------------------- #
# The guard
# --------------------------------------------------------------------------- #

def test_the_published_arm_reproduces_the_committed_artifact(vc):
    """Within float tolerance, not byte-for-byte — see tests/reproduction.py.

    If this fails, Gate 4's contrasts are being measured against a moved baseline
    while still being labelled Gate 1's.

    The exact results in this file are `Fraction`s rendered with `str`, so they are
    string leaves and still compare exactly; the grid crosscheck's columns are floats
    and are the reason a byte comparison cannot hold across CPython versions.
    """
    rows, source = vc.load_arm("published")
    findings = vc.build_findings(rows, source, grid=60)
    rendered = json.dumps(findings, indent=2, default=str)
    reproduction.assert_reproduces(rendered, COMMITTED)


def test_the_published_source_string_is_the_one_gate_one_wrote(vc):
    assert vc.ARM_SOURCES["published"] == str(vc.RUN_JSON.relative_to(vc.ROOT))
    assert json.loads(COMMITTED.read_text())["source"] == vc.ARM_SOURCES["published"]


def test_the_committed_artifact_carries_no_timestamp():
    """Byte-reproduction is only possible because Gate 1 wrote no generated_at."""
    assert "generated_at" not in json.loads(COMMITTED.read_text())


# --------------------------------------------------------------------------- #
# The arm selector
# --------------------------------------------------------------------------- #

def test_the_default_arm_is_published(vc):
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=vc.ARMS, default="published")
    assert ap.parse_args([]).arm == "published"
    assert vc.ARMS[0] == "published"


def test_the_four_arms_are_the_pre_registered_ones(vc):
    assert vc.ARMS == ("published", "rebaselined", "raw", "calibrated")
    assert set(vc.ARM_SOURCES) == set(vc.ARMS)


def test_load_arm_rejects_an_unknown_arm(vc):
    with pytest.raises(vc.ArmError, match="unknown arm"):
        vc.load_arm("fresh_calibrated")


@pytest.mark.parametrize("arm", ["published", "rebaselined", "raw", "calibrated"])
def test_every_arm_carries_all_100_cases_and_both_splits(vc, arm):
    rows, source = vc.load_arm(arm)
    assert len(rows) == 100
    assert len({r["case_id"] for r in rows}) == 100
    assert {r["split"] for r in rows} == {"dev", "test"}
    assert source == vc.ARM_SOURCES[arm]


@pytest.mark.parametrize("arm", ["rebaselined", "raw", "calibrated"])
def test_the_fresh_arms_cover_the_same_cases_as_the_published_one(vc, arm):
    published, _ = vc.load_arm("published")
    fresh, _ = vc.load_arm(arm)
    assert ({r["case_id"] for r in fresh} == {r["case_id"] for r in published})
    assert ({(r["case_id"], r["split"]) for r in fresh}
            == {(r["case_id"], r["split"]) for r in published})
    by_id = {r["case_id"]: r for r in published}
    for row in fresh:
        assert row["constraints"] == list(by_id[row["case_id"]]["constraints"] or ())


@pytest.mark.parametrize("arm", ["rebaselined", "raw", "calibrated"])
def test_every_arm_row_is_a_valid_belief(vc, arm):
    rows, _ = vc.load_arm(arm)
    for row in rows:
        b = vc.belief_of(row)
        assert abs(sum(b.readiness.values()) - 1.0) < 1e-9
        assert 0.0 <= b.needs_human <= 1.0


def test_the_three_fresh_arms_share_one_readiness_vector(vc):
    """What makes each contrast one-variable: only needs_human moves."""
    arms = {a: {r["case_id"]: r["belief"]["readiness"]
                for r in vc.load_arm(a)[0]}
            for a in ("rebaselined", "raw", "calibrated")}
    assert arms["rebaselined"] == arms["raw"] == arms["calibrated"]


# --------------------------------------------------------------------------- #
# The two pre-registered falsifiers that are properties of the committed map
# --------------------------------------------------------------------------- #

def test_the_committed_knots_reproduce_the_committed_calibrated_scores(vc):
    """Falsifier: the stored knots and the stored scores are two records of one
    thing. `_committed_scores` raises above 1e-12; this asserts it does not."""
    scores = vc._committed_scores(vc._load_elicitation())
    assert len(scores) == 100
    assert all({"raw", "calibrated", "split"} <= set(v) for v in scores.values())


def test_no_calibrated_score_sits_below_the_map_floor(elicitation):
    cal = elicitation["analysis"]["calibration"]
    floor = cal["map"]["knots"][0][1]
    scores = elicitation["analysis"]["recalibrated_scores"]
    assert min(v["calibrated"] for v in scores.values()) >= floor


def test_the_floor_is_six_twentythirds_and_sits_above_both_thresholds(elicitation):
    """The Gate 4 headline as an assertion.

    `1/5 < 3/13 < 6/23` is why calibration structurally excludes the
    constrained-menu positive-VoI region and puts every case above t*. The floor is
    the lowest pooled PAVA block's positive rate, so it is exactly rational.
    """
    floor = elicitation["analysis"]["calibration"]["map"]["knots"][0][1]
    assert floor == float(ISOTONIC_FLOOR)
    assert POSITIVE_VOI_BOUND < T_STAR < ISOTONIC_FLOOR


def test_the_map_is_weakly_monotone_so_it_merges_rather_than_reorders(elicitation):
    """What `order_preserved_on_test: false` actually means.

    Isotonic cannot invert two cases; it can only send them to the same value. The
    flag is about ties, and the write-up has to say so rather than implying the
    ordering was scrambled.
    """
    knots = elicitation["analysis"]["calibration"]["map"]["knots"]
    ys = [y for _, y in knots]
    assert ys == sorted(ys)
    assert elicitation["analysis"]["calibration"]["order_preserved_on_test"] is False
    assert elicitation["analysis"]["calibration"]["map"]["strictly_monotone"] is False


# --------------------------------------------------------------------------- #
# Section 4 of the pre-registration, as a structural assertion
# --------------------------------------------------------------------------- #

def test_the_belief_independent_checks_cannot_read_an_arm(vc):
    """No arm can move the closed-form results, and this is why.

    `check_global_ceiling`, `check_feasibility`, `lambda_crosscheck`,
    `witness_crosscheck` and `grid_crosscheck` take no rows, so the claim that
    -2/13 survives recalibration is a property of the cost matrix rather than a
    measurement on any belief set. Asserted structurally so a future edit that
    threads rows into one of them fails here instead of quietly turning a tautology
    into something that looks like a finding.
    """
    for name in ("check_global_ceiling", "check_feasibility", "lambda_crosscheck",
                 "witness_crosscheck", "grid_crosscheck"):
        params = inspect.signature(getattr(vc, name)).parameters
        assert "rows" not in params, f"{name} now reads rows"


def test_only_the_case_level_checks_read_an_arm(vc):
    for name in ("check_per_case", "check_constrained_regime", "check_invariants"):
        params = inspect.signature(getattr(vc, name)).parameters
        assert "rows" in params, f"{name} no longer reads rows"


def test_the_arm_selector_makes_no_api_calls():
    """Structural, matching the Gate 3 guard: no provider name in the module."""
    src = (ROOT / "experiments" / "voi_ceiling.py").read_text(encoding="utf-8")
    for forbidden in ("get_belief", "llm_chain", "openai", "genai",
                      "get_provider", "requests"):
        assert forbidden not in src, f"{forbidden} appears in voi_ceiling.py"


def test_the_arms_script_makes_no_api_calls():
    src = (ROOT / "experiments" / "voi_ceiling_arms.py").read_text(encoding="utf-8")
    for forbidden in ("get_belief", "llm_chain", "openai", "genai",
                      "get_provider", "requests"):
        assert forbidden not in src, f"{forbidden} appears in voi_ceiling_arms.py"


# --------------------------------------------------------------------------- #
# The four-arm report
# --------------------------------------------------------------------------- #

def test_the_arms_report_reproduces_the_committed_artifact(vca, report):
    """The arms artifact carries no timestamp, so it is reproducible from cache."""
    rendered = json.dumps(report, indent=2, default=str)
    reproduction.assert_reproduces(rendered, COMMITTED_ARMS)


def test_the_arms_markdown_reproduces_the_committed_artifact(vca, report):
    assert vca.render(report) + "\n" == COMMITTED_ARMS_MD.read_text(encoding="utf-8")


def test_the_report_is_deterministic(vca, report):
    again = vca.build_report(grid=60)
    assert json.dumps(again, default=str) == json.dumps(report, default=str)


def test_no_arm_has_a_positive_ceiling_on_any_split(report):
    """The result. Not one of the 400 case-level ceilings is positive."""
    for arm in report["arms"]:
        for split, stats in report["per_arm"][arm]["ceiling"].items():
            assert stats["n_positive_ceiling"] == 0, f"{arm} / {split}"
            assert stats["max_ceiling"] < 0


def test_ask_is_never_the_myopic_argmin_on_any_arm(report):
    for arm in report["arms"]:
        inv = report["per_arm"][arm]["invariants"]
        assert inv["cases_where_ask_would_be_chosen"] == []
        assert inv["ask_never_myopic_argmin"] == "100/100"


def test_no_constrained_case_reaches_the_positive_region_on_any_arm(report):
    for arm in report["arms"]:
        c = report["per_arm"][arm]["constrained_cases"]
        assert c["n"] == 8
        assert c["any_inside_the_region"] is False
        assert c["min_b_h"] > c["region_bound_b_h_below"]


# --------------------------------------------------------------------------- #
# Section 4 of the pre-registration, as a value-level assertion
# --------------------------------------------------------------------------- #

def test_the_belief_independent_sections_are_identical_across_arms(report):
    bi = report["belief_independent"]
    assert bi["identical_across_all_arms"] is True
    assert bi["unconstrained_max_ceiling_exact"] == "-2/13"
    assert bi["ask_can_ever_be_rational_unconstrained"] is False
    assert bi["t_star_exact"] == str(T_STAR)
    assert bi["general_condition_ratio_exact"] == "16/15"
    assert bi["general_condition_satisfied"] is False
    assert bi["constrained_positive_region"]["b_h_upper_bound_exact"] == "1/5"


def test_a_belief_dependent_closed_form_section_is_refused(vca):
    """Negative control on the agreement check.

    The point of comparing the closed-form sections across arms is to catch a future
    edit that lets beliefs leak into one of them. Doctor one arm's copy and confirm
    the check refuses rather than quietly reporting the reference arm's value four
    times over.
    """
    findings = {arm: {k: {"v": 1} for k in vca.BELIEF_INDEPENDENT}
                for arm in vca.vc.ARMS}
    for arm in vca.vc.ARMS:
        findings[arm]["constrained_regime"] = {"max_ceiling": 1.0}
    findings["calibrated"]["global_ceiling"] = {"v": 2}
    with pytest.raises(vca.ArmsError, match="belief-independent sections differ"):
        vca.belief_independent_agreement(findings)


def test_a_disagreeing_constrained_maximum_is_refused(vca):
    findings = {arm: {k: {"v": 1} for k in vca.BELIEF_INDEPENDENT}
                for arm in vca.vc.ARMS}
    for i, arm in enumerate(vca.vc.ARMS):
        findings[arm]["constrained_regime"] = {"max_ceiling": float(i)}
    with pytest.raises(vca.ArmsError, match="constrained_regime.max_ceiling"):
        vca.belief_independent_agreement(findings)


# --------------------------------------------------------------------------- #
# The calibration floor, as reported
# --------------------------------------------------------------------------- #

def test_the_reported_floor_is_the_exact_rational(report):
    cf = report["calibration_floor"]
    assert cf["reachable_range"]["low_exact"] == str(ISOTONIC_FLOOR)
    assert cf["reachable_range"]["high_exact"] == "1"
    assert cf["ordering"]["holds"] is True
    assert cf["ordering"]["as_written"] == "1/5 < 3/13 < 6/23"
    assert cf["ordering"]["gaps"]["floor_minus_t_star_exact"] == "9/299"
    assert cf["ordering"]["gaps"]["floor_minus_region_bound_exact"] == "7/115"


def test_every_pava_block_level_equals_its_own_positive_rate(report):
    m = report["calibration_floor"]["mechanism"]
    assert m["every_level_equals_positives_over_n"] is True
    assert m["recovered_without_refitting"] is True
    assert len(m["blocks"]) == 12
    assert m["blocks"][0]["n_dev_cases"] == 23
    assert m["blocks"][0]["positives"] == 6
    assert m["blocks"][0]["level_exact"] == str(ISOTONIC_FLOOR)
    assert sum(b["n_dev_cases"] for b in m["blocks"]) == 50
    assert sum(b["positives"] for b in m["blocks"]) == 21
    assert m["dev_base_rate_exact"] == "21/50"
    for b in m["blocks"]:
        assert b["level_exact"] == str(Fraction(b["positives"], b["n_dev_cases"]))


def test_a_doctored_block_level_is_refused(vca, elicitation):
    """Negative control on the block recovery.

    `_dev_blocks` is what turns "the floor is 6/23" into "the floor is 6/23 BECAUSE
    the lowest block pooled 23 dev cases with 6 positives". Move a knot's level and
    the recovery must refuse, or the mechanism claim is decoration.
    """
    knots = [list(k) for k in elicitation["analysis"]["calibration"]["map"]["knots"]]
    knots[0][1] = 0.25
    scores = elicitation["analysis"]["recalibrated_scores"]
    labels = {c["case_id"]: c["labels"]["needs_human"] for c in
              json.loads((ROOT / "data" / "cases.json").read_text())["cases"]}
    with pytest.raises(vca.ArmsError, match="two records of one fit"):
        vca._dev_blocks([tuple(k) for k in knots], scores, labels)


def test_no_calibrated_arm_belief_is_below_the_floor(vca):
    rows, _ = vca.vc.load_arm("calibrated")
    assert min(r["belief"]["needs_human"] for r in rows) == float(ISOTONIC_FLOOR)


def test_the_calibrated_arm_never_makes_answer_the_v_act_argmin(report):
    """Consequence 1 of the floor, as it shows up in the ceiling machinery."""
    census = report["per_arm"]["calibrated"]["v_act_argmin_census"]
    assert "answer" in report["per_arm"]["published"]["v_act_argmin_census"]
    assert "answer" not in census
    c = report["calibration_floor"]["consequences"][
        "answer_is_never_the_v_act_argmin_under_calibration"]
    assert c["n_calibrated_below_t_star"] == 0
    assert c["n_raw_below_t_star"] > 0


def test_the_calibrated_arm_reaches_no_belief_inside_the_positive_region(report):
    c = report["calibration_floor"]["consequences"][
        "no_calibrated_belief_reaches_the_positive_voi_region"]
    assert c["n_calibrated_below_the_bound"] == 0
    assert c["n_raw_below_the_bound"] > 0
    assert c["n_raw_below_the_bound_that_also_carry_the_constraint"] == 0
    assert c["n_calibrated_actually_inside"] == 0
    assert c["n_raw_actually_inside"] == 0
    assert c["structural_for_the_calibrated_arm"] is True
    assert c["structural_for_the_other_arms"] is False


def test_the_region_bound_is_labelled_necessary_not_sufficient(report):
    """The bound is the most favourable ray's crossover, so b_h < 1/5 does not put a
    belief in the region. The artifact has to say so or it overclaims."""
    c = report["calibration_floor"]["consequences"][
        "no_calibrated_belief_reaches_the_positive_voi_region"]
    caveat = c["region_bound_is_necessary_not_sufficient"]
    assert "not thereby inside the region" in caveat
    assert "sufficient test is the per-case ceiling" in caveat
    assert c["region_necessary_condition"] == "b_h < 1/5"
    # The sufficient test is the per-case ceiling, and it is negative everywhere.
    assert sum(report["per_arm"][a]["ceiling"]["all_100"]["n_positive_ceiling"]
               for a in report["arms"]) == 0


# --------------------------------------------------------------------------- #
# Section 3.4's first falsifier, landed as the regression guard it is
# --------------------------------------------------------------------------- #

def test_the_calibrated_arm_chooses_answer_zero_times_on_test(report):
    """Pre-registration 3.4 falsifier 1, recorded there as a regression guard.

    `results/rebaseline.json` already commits this count, so Gate 4 reproduces it
    rather than discovering it. What would be new information is the count CHANGING.
    """
    rg = report["regression_guards"]
    assert rg["status"] == "regression guard, not an open test"
    assert rg["calibrated_answer_count"] == 0
    assert rg["calibrated_chooses_answer_zero_times"] is True


@pytest.mark.parametrize("arm", ["published", "rebaselined", "raw", "calibrated"])
def test_each_arm_reproduces_its_committed_test_split_census(report, arm):
    g = report["regression_guards"]["per_arm"][arm]
    assert g["n"] == 50
    assert g["reproduces"] is True
    assert g["computed_here"] == g["committed"]


def test_the_committed_censuses_are_read_from_rebaseline_json(report):
    """The guard compares against a file, not against numbers typed into this test."""
    committed = json.loads(REBASELINE.read_text(encoding="utf-8"))
    assert committed["split"] == "test"
    assert (report["regression_guards"]["per_arm"]["calibrated"]["committed"]
            == committed["arms"]["fresh_calibrated"]["action_counts"])
    assert (report["regression_guards"]["per_arm"]["published"]["committed"]
            == committed["published"]["test"]["action_counts"])


def test_the_tie_break_rule_does_not_change_any_arm_census(report):
    """run.json used the legacy tie-break; the arms use the current one. On the test
    split the two agree, which rebaseline.py also reports. Asserted, not assumed."""
    for arm in report["arms"]:
        assert (report["regression_guards"]["per_arm"][arm]
                ["tie_break_changes_the_census"] is False)
