"""
Guards on `paper/figures/make_figures.py`.

The point of this file is not that the panel numbers are right — they are read from
committed artifacts, so of course they agree with themselves. The point is that
`--check` **fails** when they stop agreeing with the per-case records those
artifacts were computed from. So most of what follows is negative controls: doctor
one committed value, assert the check catches it, name what it caught.

A check that can only pass is not a check. Every family of assertions in
`make_figures.check()` has a test here that breaks it on purpose.

The one substantive finding this file locks is the bracket. The shaded band on
panel 1 carries two claims — no case takes a value in (0.2, 0.3), and every
threshold in (0.2, 0.3] decides identically — and the version before this one wrote
the second bracket on the first claim. 17 cases sit at exactly 0.3, so the value
claim is false as it was written. Both brackets are now derived and asserted apart.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "paper" / "figures" / "make_figures.py"
RUN_JSON = ROOT / "results" / "run.json"
ELICIT_JSON = ROOT / "results" / "logprob-elicitation.json"


@pytest.fixture(scope="module")
def mf():
    spec = importlib.util.spec_from_file_location("make_figures", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def panels(mf):
    return mf.figure_data()


@pytest.fixture
def doctor(mf, monkeypatch):
    """Replace one loader with a deep-copied, mutated payload, rebuild, re-check.

    Deep-copied because the real payloads are cached at module level and a mutation
    that leaked would make every later test in the session meaningless.

    This is the within-payload route: the panels are rebuilt from the doctored
    payload, so it catches an aggregate table that disagrees with the per-case rows
    in the same file. That is the drift `--check` was written for.
    """
    def _doctor(which: str, mutate):
        path = {"run": RUN_JSON, "elicit": ELICIT_JSON}[which]
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload)
        monkeypatch.setattr(mf, f"_{which}", lambda: copy.deepcopy(payload))
        return mf.figure_data()
    return _doctor


@pytest.fixture
def stale(mf, monkeypatch, panels):
    """Check the honestly-built panels against doctored per-case records.

    Some fields — the shaded band above all — are *derived* from the records rather
    than read from a committed table, so within one payload the panel and the check
    move together and can never disagree. The failure those fields guard against is
    a panel that has gone stale relative to the data: an interval written down once
    and left behind when the beliefs moved. That is what happened to the bracket in
    `paper/main.tex`, so it is tested with the pair deliberately mismatched.
    """
    def _stale(which: str, mutate):
        path = {"run": RUN_JSON, "elicit": ELICIT_JSON}[which]
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload)
        frozen = copy.deepcopy(panels)
        monkeypatch.setattr(mf, f"_{which}", lambda: copy.deepcopy(payload))
        return mf.check(frozen)
    return _stale


def _first_matching(bad: list[str], needle: str) -> str:
    hits = [line for line in bad if needle in line]
    assert hits, f"no mismatch mentioning {needle!r}; got {bad}"
    return hits[0]


# --------------------------------------------------------------------------- #
# The check passes on the committed artifacts
# --------------------------------------------------------------------------- #

def test_check_passes_on_the_committed_artifacts(mf, panels):
    assert mf.check(panels) == []


def test_main_exits_zero_under_check(mf, monkeypatch, capsys):
    import sys
    monkeypatch.setattr(sys, "argv", ["make_figures.py", "--check"])
    assert mf.main() == 0
    out = capsys.readouterr().out
    assert "check passed" in out
    assert "CHECK FAILED" not in out


def test_check_mode_never_reaches_the_renderer(mf, monkeypatch, capsys):
    """matplotlib is absent here, so a stray render call would be an ImportError
    dressed up as a figure. --check must return before it."""
    import sys

    def _boom(_data):
        raise AssertionError("render was called under --check")
    monkeypatch.setattr(mf, "render", _boom)
    monkeypatch.setattr(sys, "argv", ["make_figures.py", "--check"])
    assert mf.main() == 0
    capsys.readouterr()


def test_a_doctored_panel_makes_main_exit_non_zero(mf, monkeypatch, capsys):
    import sys
    payload = json.loads(RUN_JSON.read_text(encoding="utf-8"))
    payload["summaries"]["all"]["calibration"]["needs_human"]["ece"] = 0.9
    monkeypatch.setattr(mf, "_run", lambda: copy.deepcopy(payload))
    monkeypatch.setattr(sys, "argv", ["make_figures.py", "--check"])
    assert mf.main() == 1
    assert "CHECK FAILED" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Panel 1 negative controls
# --------------------------------------------------------------------------- #

def test_a_wrong_bin_count_is_caught(mf, doctor):
    def mutate(p):
        p["summaries"]["all"]["calibration"]["needs_human"]["bins"][2]["n"] = 34
    bad = mf.check(doctor("run", mutate))
    assert "recount 35 against committed 34" in _first_matching(bad, "v1 bin 0.2-0.3")


def test_a_wrong_mean_predicted_is_caught(mf, doctor):
    def mutate(p):
        b = p["summaries"]["all"]["calibration"]["needs_human"]["bins"][2]
        b["mean_predicted"] = 0.25
    bad = mf.check(doctor("run", mutate))
    _first_matching(bad, "mean_predicted")


def test_a_wrong_observed_frequency_is_caught(mf, doctor):
    def mutate(p):
        b = p["summaries"]["all"]["calibration"]["needs_human"]["bins"][2]
        b["observed_frequency"] = 0.2
    bad = mf.check(doctor("run", mutate))
    _first_matching(bad, "observed")


def test_a_wrong_ece_is_caught(mf, doctor):
    def mutate(p):
        p["summaries"]["all"]["calibration"]["needs_human"]["ece"] = 0.15
    bad = mf.check(doctor("run", mutate))
    _first_matching(bad, "v1 ece")


def test_a_rate_that_recovers_the_wrong_positive_count_is_caught(mf, doctor):
    """The Wilson bars are drawn from a count recovered by un-rounding the committed
    rate. If that recovery is wrong the bars are wrong even when the table looks fine.

    For n=35 the 4dp rate comparison necessarily fires alongside this one — a rate
    within 5e-5 of k/n cannot recover a different integer at that n. The check exists
    so the error-bar input is verified in its own right rather than inferred from the
    plotted rate, not because it can fire alone at this sample size.
    """
    def mutate(p):
        cal = p["summaries"]["all"]["calibration"]["needs_human"]
        b = next(b for b in cal["bins"] if b["n"] == 35)
        # The true count is 6 of 35 = 0.1714. 0.1858 * 35 = 6.503, which rounds to 7.
        b["observed_frequency"] = 0.1858
    bad = mf.check(doctor("run", mutate))
    assert "recovers 7 positives, not 6" in _first_matching(bad, "positives")


def test_a_case_landing_inside_the_value_gap_is_caught(stale):
    """The band is derived, so this is the stale-panel route: the committed interval
    says (0.2, 0.3) is empty and a belief has since moved into it."""
    def mutate(p):
        p["rows"][0]["belief"]["needs_human"] = 0.25
    bad = stale("run", mutate)
    assert "1 cases strictly inside the value gap" in _first_matching(
        bad, "strictly inside the value gap")


def test_a_derived_band_moves_with_the_data_rather_than_going_stale(mf, doctor):
    """The other half of the same point. Rebuilt from the moved beliefs, the panel
    reports the new gap and the check passes — the interval is not hard-coded."""
    def mutate(p):
        p["rows"][0]["belief"]["needs_human"] = 0.25
    panels = doctor("run", mutate)
    assert panels["v1_needs_human"]["empty_value_interval"]["interval"] == [0.2, 0.25]
    assert not any("value gap" in line for line in mf.check(panels))


def test_a_committed_n_disagreeing_with_the_row_count_is_caught(mf, doctor):
    def mutate(p):
        p["summaries"]["all"]["calibration"]["needs_human"]["n"] = 99
    bad = mf.check(doctor("run", mutate))
    assert "100 rows in run.json against n=99" in _first_matching(
        bad, "rows in run.json")


# --------------------------------------------------------------------------- #
# The bracket, which is the finding this file exists to lock
# --------------------------------------------------------------------------- #

def test_the_two_intervals_share_endpoints_and_differ_in_bracket(panels):
    v1 = panels["v1_needs_human"]
    gap = v1["empty_value_interval"]
    band = v1["equivalent_threshold_interval"]
    assert gap["interval"] == band["interval"] == [0.2, 0.3]
    assert gap["closed"] == "(lo, hi)"
    assert band["closed"] == "(lo, hi]"
    assert gap["closed"] != band["closed"]


def test_seventeen_cases_sit_at_the_top_of_the_value_gap(mf, panels):
    """Which is why the gap is open there. If this ever became zero the two
    brackets would coincide and the distinction would be pedantry."""
    assert "17 cases sit at exactly 0.3" == \
        panels["v1_needs_human"]["empty_value_interval"]["why_open_at_the_top"]
    rows = mf._run()["rows"]
    assert sum(1 for r in rows if r["belief"]["needs_human"] == 0.3) == 17


def test_the_threshold_band_is_verified_as_a_partition_identity(mf, panels):
    """Not inferred from the emptiness of the value gap. A threshold at 0.3 has to
    decide as 3/13 does, and 0.2 and 0.4 have to differ from it."""
    rows = mf._run()["rows"]

    def part(t):
        return frozenset(r["case_id"] for r in rows
                         if r["belief"]["needs_human"] < t)

    at = part(mf.THRESHOLD)
    assert part(0.3) == at
    assert part(0.2) != at
    assert part(0.4) != at
    assert len(at) == 54


def test_a_band_closed_where_it_should_be_open_is_caught(stale):
    """Move the 17 cases off 0.3 and the gap should close there, making the two
    brackets coincide. Checked on the stale route, since a rebuilt panel would
    simply redraw the band — the failure is a band that outlived its justification."""
    def mutate(p):
        for r in p["rows"]:
            if r["belief"]["needs_human"] == 0.3:
                r["belief"]["needs_human"] = 0.4
    bad = stale("run", mutate)
    assert any("brackets should not differ" in line for line in bad), bad


def test_the_render_label_carries_both_brackets(mf):
    import inspect
    src = inspect.getsource(mf.render)
    assert "({lo:g}, {hi:g}]$" in src, "the threshold band must be closed at the top"
    assert "({lo:g}, {hi:g})$" in src, "the value gap must be open at the top"


# --------------------------------------------------------------------------- #
# Panels 2 and 3: the Gate 2 test-split data path
# --------------------------------------------------------------------------- #

def test_both_gate2_panels_are_present_and_test_split(panels):
    for which in ("raw", "calibrated"):
        p = panels[f"gate2_test_{which}"]
        assert p["n"] == 50
        assert p["base_rate"] == 0.42
        assert len(p["bins"]) == 10
        assert "test cases" in p["population"]


def test_the_gate2_panels_declare_no_render_path(panels):
    for which in ("raw", "calibrated"):
        p = panels[f"gate2_test_{which}"]
        assert p["renders"] is False
        assert "paper gate" in p["render_deferred_to"]
    assert panels["v1_needs_human"]["renders"] is True


def test_gate2_panels_carry_all_three_committed_metrics(mf, panels):
    cal = mf._elicit()["analysis"]["calibration"]
    for which in ("raw", "calibrated"):
        p = panels[f"gate2_test_{which}"]
        committed = cal[f"test_{which}"]
        for key in ("ece", "brier", "cross_entropy_bits", "base_rate", "n"):
            assert p[key] == committed[key]


def test_the_map_improves_all_three_metrics_on_test(panels):
    """Gate 2's result, restated here only so the panels cannot silently swap."""
    raw = panels["gate2_test_raw"]
    cal = panels["gate2_test_calibrated"]
    for key in ("ece", "brier", "cross_entropy_bits"):
        assert cal[key] < raw[key]


def test_empty_bins_survive_in_the_gate2_panels(panels):
    """run.json drops them; the Gate 2 tables keep them. A panel that quietly
    dropped them would draw a line across a region holding no evidence."""
    assert panels["gate2_test_raw"]["empty_bins"] == ["0.9-1.0"]
    assert panels["gate2_test_calibrated"]["empty_bins"] == [
        "0.0-0.1", "0.1-0.2", "0.6-0.7", "0.8-0.9"]


@pytest.mark.parametrize("which", ["raw", "calibrated"])
def test_a_wrong_gate2_bin_count_is_caught(mf, doctor, which):
    def mutate(p):
        table = p["analysis"]["calibration"][f"test_reliability_{which}"]
        occupied = next(b for b in table if b["n"] > 1)
        occupied["n"] -= 1
    bad = mf.check(doctor("elicit", mutate))
    _first_matching(bad, f"{which} bin")


@pytest.mark.parametrize("which", ["raw", "calibrated"])
@pytest.mark.parametrize("metric", ["ece", "brier", "cross_entropy_bits"])
def test_a_wrong_gate2_metric_is_caught(mf, doctor, which, metric):
    def mutate(p):
        p["analysis"]["calibration"][f"test_{which}"][metric] += 0.01
    bad = mf.check(doctor("elicit", mutate))
    _first_matching(bad, f"{which} {metric}")


@pytest.mark.parametrize("which", ["raw", "calibrated"])
def test_a_wrong_gate2_mean_score_is_caught(mf, doctor, which):
    def mutate(p):
        table = p["analysis"]["calibration"][f"test_reliability_{which}"]
        occupied = next(b for b in table if b["n"] > 1)
        occupied["mean_score"] = round(occupied["mean_score"] + 0.05, 4)
    bad = mf.check(doctor("elicit", mutate))
    _first_matching(bad, "mean_score")


def test_a_split_relabelled_to_test_is_caught(mf, doctor):
    """The panels are held-out claims. Widening the population is the failure this
    catches, and it is the one that would flatter the map most."""
    def mutate(p):
        for row in p["analysis"]["recalibrated_scores"].values():
            row["split"] = "test"
    bad = mf.check(doctor("elicit", mutate))
    assert any("100 test cases against committed n=50" in line for line in bad), bad


def test_a_scored_case_with_no_label_raises_rather_than_shrinking_the_panel(
        mf, monkeypatch):
    payload = json.loads(RUN_JSON.read_text(encoding="utf-8"))
    payload["rows"] = [r for r in payload["rows"] if r["split"] != "test"]
    monkeypatch.setattr(mf, "_run", lambda: copy.deepcopy(payload))
    with pytest.raises(KeyError, match="carries no label"):
        mf._test_pairs("raw")


# --------------------------------------------------------------------------- #
# The calibration floor, on the panel where it is the point
# --------------------------------------------------------------------------- #

def test_the_calibrated_panel_carries_the_unreachable_region(panels):
    r = panels["gate2_test_calibrated"]["unreachable_region"]
    assert r["floor_exact"] == "6/23"
    assert r["floor"] == pytest.approx(6 / 23, abs=1e-15)
    assert r["interval"] == [0.0, r["floor"]]
    assert r["closed"] == "[lo, hi)"
    assert r["threshold_inside"] is True
    assert "unreachable" in r["kind"]


def test_the_raw_panel_has_no_unreachable_region(panels):
    """And says why, rather than carrying the calibrated panel's caption. The two
    kinds of emptiness are not the same kind and are not merged."""
    r = panels["gate2_test_raw"]["unreachable_region"]
    assert r["interval"] is None
    assert r["kind"] == "none"
    assert "these 50 cases" in r["cause"]


def test_no_calibrated_test_score_reaches_below_the_threshold(panels):
    assert panels["gate2_test_calibrated"]["n_cases_below_threshold"] == 0
    assert panels["gate2_test_raw"]["n_cases_below_threshold"] == 24


def test_a_score_below_the_floor_is_caught(mf, doctor):
    def mutate(p):
        first = sorted(p["analysis"]["recalibrated_scores"])
        for case_id in first:
            if p["analysis"]["recalibrated_scores"][case_id]["split"] == "test":
                p["analysis"]["recalibrated_scores"][case_id]["calibrated"] = 0.1
                break
    bad = mf.check(doctor("elicit", mutate))
    assert any("below a floor claimed unreachable" in line for line in bad), bad


def test_a_moved_floor_is_caught(mf, doctor):
    def mutate(p):
        p["analysis"]["calibration"]["map"]["knots"][0][1] = 0.2
    bad = mf.check(doctor("elicit", mutate))
    assert any("is not 6/23" in line for line in bad), bad


# --------------------------------------------------------------------------- #
# Why the three panels are not one figure
# --------------------------------------------------------------------------- #

def test_the_bin_widths_do_match_and_the_artifact_says_so(panels):
    """The pre-registration described these as two bin schemes. They are one
    scheme: ten equal-width bins and the same index rule on all three panels.
    What differs is the population, the score source and empty-bin survival."""
    w = panels["why_the_panels_are_not_one_figure"]
    assert w["bin_width_is_shared"] is True
    assert w["populations"] == {"v1_needs_human": 100, "gate2_test_raw": 50,
                               "gate2_test_calibrated": 50}
    assert w["empty_bins_dropped_at_source"] == {
        "v1_needs_human": True, "gate2_test_raw": False,
        "gate2_test_calibrated": False}
    assert "the bin widths do match" in w["note"]


def test_the_bin_index_rule_is_restated_not_imported(mf):
    """Re-deriving a committed number with the function that wrote it checks
    nothing. `src.calibrate` is deliberately absent from this module."""
    import inspect
    src = inspect.getsource(mf)
    assert "import calibrate" not in src
    assert "from src" not in src
    assert mf._bin_index(1.0, 10) == 9
    assert mf._bin_index(0.0, 10) == 0
    assert mf._bin_index(0.3, 10) == 3


def test_every_declared_panel_is_built(mf, panels):
    for name in mf.PANELS:
        assert name in panels
        assert panels[name]["panel"] == name


# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #

def test_no_forbidden_vocabulary(mf):
    text = SCRIPT.read_text(encoding="utf-8").lower()
    for word in ("cohort", "deliverable", "arthryx", "whatsapp", "real estate"):
        assert word not in text
