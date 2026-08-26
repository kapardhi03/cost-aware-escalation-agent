"""
Guards on `experiments/entropy_baseline.py`.

The sign of every excess in this gate is inherited, not discovered: all 400 committed
per-case ceilings are negative and the unconstrained-menu maximum is -2/13 in closed
form. So a test that asserts the excesses are positive proves nothing about the code.
What is worth testing is the machinery that would notice if they stopped being
positive, and the arithmetic that turns the sign into a magnitude. Most of what
follows is therefore negative controls: break one input on purpose, assert the guard
raises, name what it caught.

Three checks carry the weight.

`ceiling_agreement` is the real cross-check on the VoI computation, and it is exact:
`EC(ask) - V_act` recomputed here equals the committed per-case ceiling to 0.0 on all
four arms. Invariant 6 is not that check. Its slack equals `V_q` to 7.8e-16, so on
these definitions it reduces to `V_q >= 0`, which every non-negative cost matrix
satisfies for free. `test_invariant_6_is_not_independent_evidence` pins that down so
the claim cannot quietly re-inflate.

The per-arm fallback reference is the second. v1's policy scores 86 on published, 70
on raw and 75 on calibrated, all committed in Gate 2. An earlier version of the render
printed published's 86 as the reference for all four arms while computing the excess
column against each arm's own total, so raw's `+7.70` was labelled against a total raw
never had. The arms are now checked against `results/rebaseline.json` one at a time.

The third is the expected/realised split. The expected tiers must fall as tau rises —
nested firing sets, positive per-case excess — and that is asserted. The realised
column has no such guarantee, and on the rebaselined arm it inverts once:
`a02-deep-017` leaves the firing set, v1 answers it for a realised 10 where
ask-then-act realised 6, and the total rises while the firing count falls. Its
expected excess is +0.40 throughout. Both facts are locked here, because the honest
reading of the pair is the point: the ceiling bounds expected cost and says nothing
about a single realised draw.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest

import reproduction

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "entropy_baseline.py"
COMMITTED_JSON = ROOT / "results" / "entropy-baseline.json"
COMMITTED_MD = ROOT / "results" / "entropy-baseline.md"
REBASELINE = ROOT / "results" / "rebaseline.json"
CEILING_ARMS = ROOT / "results" / "voi-ceiling-arms.json"
PREREG = ROOT / "decisions" / "v2-gate5-preregistration.md"


@pytest.fixture(scope="module")
def eb():
    spec = importlib.util.spec_from_file_location("entropy_baseline", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report(eb):
    return eb.build_report()


@pytest.fixture(scope="module")
def rebaseline():
    return json.loads(REBASELINE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cases(eb):
    """Per-case records for one arm, for the tests that need the raw rows."""
    rows, _ = eb.vc.load_arm("published")
    return eb.per_case(rows)


# --------------------------------------------------------------------------- #
# The guard: the committed artifacts still come out of the code
# --------------------------------------------------------------------------- #

def test_json_reproduces_within_float_tolerance(eb, report):
    """Not byte-for-byte: this artifact carries float sums. See tests/reproduction.py.

    Every leaf that is not a float-versus-float pair — every count, every question id,
    every bool, and the key order itself — still has to match exactly.
    """
    reproduction.assert_reproduces(json.dumps(report, indent=2) + "\n",
                                   COMMITTED_JSON)


def test_md_reproduces_byte_for_byte(eb, report):
    assert eb.render(report) == COMMITTED_MD.read_text(encoding="utf-8")


def test_no_timestamp_anywhere(eb, report):
    blob = json.dumps(report) + eb.render(report)
    assert "generated_at" not in blob
    assert not re.search(r"20\d\d-\d\d-\d\dT", blob)


def test_two_builds_agree(eb, report):
    again = eb.build_report()
    assert json.dumps(again, sort_keys=True) == json.dumps(report, sort_keys=True)


# --------------------------------------------------------------------------- #
# The cost-side adapter
# --------------------------------------------------------------------------- #

def test_adapter_agrees_with_costs_expected_cost(report):
    ad = report["adapter"]
    assert ad["within_tol"] is True
    assert ad["n_comparisons"] == 500
    assert ad["max_abs_delta"] == 0.0


def test_the_adapter_is_needed_because_narrow_refuses_coupled_posteriors(eb):
    """Negative control on the reason the adapter exists, not on the adapter.

    If `narrow` ever started projecting a coupled posterior onto its marginals, this
    test would fail and `ec_joint` would become dead weight that silently hid the
    coupling. The committed coupled example is `a01-first-001` on `q_specifics`.
    """
    from src.belief import Belief
    from src.questions import NonFactorisingError

    rows, _ = eb.vc.load_arm("published")
    row = next(r for r in rows if r["case_id"] == "a01-first-001")
    b = Belief.from_dict(row["belief"])
    joint = eb.widen(b.readiness, b.needs_human)
    q = next(q for q in eb.QUESTIONS if q.id == "q_specifics")

    coupled = [post for _u, p_u, post in eb.posteriors_for(q, joint)
               if p_u > 0 and not eb.factorises(post, 1e-12)]
    assert coupled, "q_specifics no longer couples on this case; the adapter's " \
                    "justification needs rewriting, not the test relaxing"

    from src import questions as sq
    with pytest.raises(NonFactorisingError):
        sq.narrow(coupled[0], 1e-12)

    # And the adapter prices it anyway, which is the whole point.
    assert eb.ec_joint("ask", coupled[0]) >= 0.0


def test_a_doctored_matrix_makes_the_adapter_disagree(eb):
    """Negative control: the adapter comparison has to be able to fail."""
    from src.belief import Belief

    rows, _ = eb.vc.load_arm("published")
    bent = copy.deepcopy(eb.costs.COST)
    for s in bent["ask"]:
        bent["ask"][s] += 1.0

    b = Belief.from_dict(rows[0]["belief"])
    joint = eb.widen(b.readiness, b.needs_human)
    straight = eb.ec_joint("ask", joint)
    crooked = eb.ec_joint("ask", joint, matrix=bent)
    assert crooked == pytest.approx(straight + 1.0)


# --------------------------------------------------------------------------- #
# The real cross-check on the VoI computation
# --------------------------------------------------------------------------- #

def test_ceiling_agreement_is_exact_on_every_arm(eb, report):
    for arm in eb.ARMS:
        ca = report["arms"][arm]["ceiling_agreement"]
        assert ca["n_cases"] == 100, arm
        assert ca["max_ceiling_delta"] == 0.0, arm
        assert ca["max_ec_ask_delta_from_2_plus_2bh"] < 1e-14, arm
        assert ca["max_v_act_recovery_delta"] < 1e-14, arm
        assert ca["n_cases_with_non_positive_tier1_excess"] == 0, arm


def test_a_doctored_committed_ceiling_is_caught(eb, cases):
    """Negative control: recomputation has to be able to disagree."""
    committed = json.loads(CEILING_ARMS.read_text(encoding="utf-8"))
    bad = copy.deepcopy(committed)
    bad["per_arm"]["published"]["per_case"][0]["ceiling"] -= 0.5

    with pytest.raises(eb.BaselineError, match="disagrees with the committed ceiling"):
        eb.ceiling_agreement("published", cases, bad)


def test_a_non_positive_excess_raises_rather_than_reporting(eb, cases):
    """The sign is pre-committed, so a violation is a bug and must not render.

    Pre-registration section 5: a non-positive excess would contradict a committed
    invariant, so the code raises instead of reporting it as a finding.

    Doctoring the excess alone would trip the ceiling comparison first, which is a
    different guard. So the committed ceiling and `v_act` are moved with it, leaving
    the sign check as the only thing left to fail. That is what makes this a control on
    the sign guard rather than on the agreement check.
    """
    committed = json.loads(CEILING_ARMS.read_text(encoding="utf-8"))
    bad = copy.deepcopy(committed)
    bent = copy.deepcopy(cases)

    target = bent[0]
    ref = next(r for r in bad["per_arm"]["published"]["per_case"]
               if r["case_id"] == target["case_id"])
    target["tier1_excess"] = -1.0
    ref["ceiling"] = 1.0
    target["v_act"] = ref["ceiling"] + target["ec_ask"]

    with pytest.raises(eb.BaselineError, match="bug, not a finding"):
        eb.ceiling_agreement("published", bent, bad)


# --------------------------------------------------------------------------- #
# The invariants, and what invariant 6 is actually worth
# --------------------------------------------------------------------------- #

def test_invariants_2_3_4_hold_on_all_400_pairs_per_arm(eb, report):
    for arm in eb.ARMS:
        iv = report["arms"][arm]["invariants"]
        assert iv["n_case_question_pairs"] == 400, arm
        assert iv["invariant_2_holds"] is True, arm
        assert iv["invariant_2_min_slack"] > -1e-14, arm
        assert iv["invariant_3_holds"] is True, arm
        assert iv["invariant_3_max_residual"] < 1e-14, arm
        assert iv["invariant_4_holds"] is True, arm
        assert iv["invariant_4_max_residual"] < 1e-14, arm


def test_invariant_4_count_is_reported_not_predicted(eb, report):
    """The pre-registration named no target for this count, and neither does this.

    What is checked is that the two ways of counting the same thing agree: a pair with
    a constant posterior argmin is exactly a pair where VoI is -EC(ask).
    """
    for arm in eb.ARMS:
        iv = report["arms"][arm]["invariants"]
        assert (iv["invariant_4_n_pairs_with_constant_argmin"]
                == iv["invariant_4_n_pairs_where_voi_is_exactly_minus_ec_ask"]), arm
        assert 0 < iv["invariant_4_n_pairs_with_constant_argmin"] < 400, arm


def test_invariant_6_is_not_independent_evidence(eb, report):
    """The correction this file exists to keep: invariant 6 reduces to `V_q >= 0`.

    Substituting VoI's definition into invariant 6 cancels `V_act` and `EC(ask)` and
    leaves `V_q >= 0`, which holds for free because every entry of `costs.COST` is
    non-negative. The pre-registration called it the cross-check that mattered most.
    It is not one. `ceiling_agreement` is, and is asserted separately above.
    """
    for arm in eb.ARMS:
        iv = report["arms"][arm]["invariants"]
        assert iv["invariant_6_holds"] is True, arm
        assert iv["invariant_6_min_slack"] >= 0.0, arm
        assert iv["invariant_6_slack_equals_v_q_max_delta"] < 1e-14, arm

    census = report["arms"]["published"]["invariants"]
    assert "reduces" in census["what_invariant_6_actually_tests"]
    assert "ceiling_agreement" in census["where_the_independent_check_is"]
    assert all(v >= 0.0 for row in eb.costs.COST.values() for v in row.values())


def test_the_bound_is_attained_not_merely_respected(eb, report):
    """Unanticipated finding: `V_q = 0` exactly on some pairs.

    A free perfect oracle that drives post-answer expected cost to zero still loses by
    the full ceiling, so the negativity cannot be blamed on slack in the bound. Raw
    has no such pair because its beliefs are continuous, which is why the assertion is
    per-arm and not global.
    """
    attained = {arm: report["arms"][arm]["invariants"]
                ["n_pairs_where_the_bound_is_attained"] for arm in eb.ARMS}
    assert attained["raw"] == 0
    assert attained["published"] > 0
    assert attained["calibrated"] > attained["published"]
    for arm, n in attained.items():
        assert 0 <= n <= 400, arm


# --------------------------------------------------------------------------- #
# The per-arm fallback reference
# --------------------------------------------------------------------------- #

def test_every_arm_is_scored_against_its_own_committed_fallback(eb, report,
                                                               rebaseline):
    for arm in eb.ARMS:
        top, key = eb.COMMITTED_FALLBACK[arm]
        ref = rebaseline[top][key]
        sw = report["arms"][arm]["threshold_sweep"]
        assert sw["reproduces_committed_fallback"] is True, arm
        assert sw["v1_fallback_realised_total"] == ref["total_cost"], arm
        assert sw["v1_fallback_realised_mean"] == pytest.approx(ref["mean_cost"]), arm


def test_the_arms_do_not_share_one_reference(eb, report):
    """The bug this check was added for: published's 86 is not raw's reference.

    If these three ever coincide the test is vacuous, so it asserts they differ.
    """
    totals = {arm: report["arms"][arm]["threshold_sweep"]["v1_fallback_realised_total"]
              for arm in ("published", "raw", "calibrated")}
    assert totals == {"published": 86, "raw": 70, "calibrated": 75}


def test_a_disagreeing_committed_fallback_is_refused(eb, cases):
    """Negative control: the per-arm comparison has to be able to fail."""
    rows, _ = eb.vc.load_arm("published")
    grid = eb.ab.tau_grid(rows)
    bad = {"total_cost": 999, "mean_cost": 19.98}
    with pytest.raises(eb.BaselineError, match="Gate 2 committed"):
        eb.threshold_sweep(cases, grid, "published", bad)


def test_the_top_of_the_grid_fires_on_nothing_and_recovers_v1(eb, report):
    for arm in eb.ARMS:
        sw = report["arms"][arm]["threshold_sweep"]
        top = sw["thresholds"][-1]
        assert top["quantile"] == 1.0, arm
        assert top["n_firing"] == 0, arm
        assert top["tier1_total_excess"] == 0.0, arm
        assert top["realised_excess_over_v1"] == 0.0, arm
        assert top["realised_total_cost"] == pytest.approx(
            sw["v1_fallback_realised_total"]), arm


def test_every_excess_is_positive_where_anything_fires(eb, report):
    """Inherited, not discovered. Asserted so a regression cannot pass silently."""
    for arm in eb.ARMS:
        for row in report["arms"][arm]["threshold_sweep"]["thresholds"]:
            if row["n_firing"] == 0:
                continue
            assert row["tier1_total_excess"] > 0.0, (arm, row["quantile"])
            assert row["tier2_total_excess"] > row["tier1_total_excess"], (
                arm, row["quantile"])


# --------------------------------------------------------------------------- #
# Expected falls with tau; realised need not
# --------------------------------------------------------------------------- #

def test_firing_sets_are_nested_and_expected_tiers_fall(eb, report):
    for arm in eb.ARMS:
        mono = report["arms"][arm]["threshold_sweep"]["monotonicity"]
        assert mono["firing_sets_are_nested"] is True, arm
        assert mono["expected_tiers_are_monotone_in_tau"] is True, arm


def test_unnested_firing_sets_raise(eb, cases):
    """Negative control: a threshold on a scalar cannot add cases as tau rises."""
    rows = [{"quantile": 0.0, "n_firing": 1, "realised_total_cost": 1.0,
             "tier1_total_excess": 1.0, "tier2_total_excess": 1.0},
            {"quantile": 0.1, "n_firing": 1, "realised_total_cost": 1.0,
             "tier1_total_excess": 1.0, "tier2_total_excess": 1.0}]
    with pytest.raises(eb.BaselineError, match="not nested"):
        eb.realised_monotonicity(cases, rows, [{"a"}, {"b"}])


def test_a_rising_expected_tier_raises(eb, cases):
    """Negative control: nested sets plus positive excesses make this impossible."""
    rows = [{"quantile": 0.0, "n_firing": 2, "realised_total_cost": 2.0,
             "tier1_total_excess": 1.0, "tier2_total_excess": 2.0},
            {"quantile": 0.1, "n_firing": 1, "realised_total_cost": 1.0,
             "tier1_total_excess": 5.0, "tier2_total_excess": 6.0}]
    with pytest.raises(eb.BaselineError, match="expected tier rose"):
        eb.realised_monotonicity(cases, rows, [{"a", "b"}, {"a"}])


def test_the_one_realised_inversion_is_reported_with_its_cause(eb, report):
    """`a02-deep-017`: v1 answers it and eats a 10; ask-then-act realised 6.

    Locked with its expected excess alongside, because the pair is the finding. The
    inversion sits on the rebaselined arm, which carries no claim, so nothing rests on
    it — but an unexplained non-monotone column would read as an arithmetic error.
    """
    inversions = {
        arm: report["arms"][arm]["threshold_sweep"]["monotonicity"]["inversions"]
        for arm in eb.ARMS}
    assert inversions["published"] == []
    assert inversions["raw"] == []
    assert inversions["calibrated"] == []

    assert len(inversions["rebaselined"]) == 1
    inv = inversions["rebaselined"][0]
    assert inv["n_firing"] == [12, 11]
    assert inv["realised_total_cost"][1] > inv["realised_total_cost"][0]

    assert len(inv["cases_that_stopped_firing"]) == 1
    d = inv["cases_that_stopped_firing"][0]
    assert d["case_id"] == "a02-deep-017"
    assert d["v1_action"] == "answer"
    assert d["v1_realised_cost"] == 10
    assert d["ask_then_act_realised_cost"] == pytest.approx(6.0)
    assert d["realised_delta_from_dropping"] == pytest.approx(4.0)
    assert d["tier1_expected_excess"] > 0.0


# --------------------------------------------------------------------------- #
# The always_ask anchor and invariant 8
# --------------------------------------------------------------------------- #

def test_ask_then_act_is_strictly_dearer_than_v1_terminal_pricing(eb, report):
    a = report["arms"]["published"]["always_ask_anchor"]
    assert a["recomputed_matches_committed"] is True
    assert a["ask_then_act_is_dearer"] is True
    assert (a["gate5_all_test_cases_ask_then_act"]["total_cost"]
            > a["v1_always_ask_committed"]["total_cost"])
    assert a["n_firing_at_tau_0th_decile"] == a["n_test_cases"]


def test_invariant_8_is_checked_on_the_published_arm_only(eb, report):
    """v1's committed actions were made on v1's beliefs.

    Asserting invariant 8 on a rebuilt arm would be asserting that recalibration
    changed nothing, which is the opposite of Gate 2's result. The other three arms
    carry the reason instead of a number.

    `recomputed_test_aggregate` carries three extra fields from `ab.score` that the
    committed row does not contain, so the comparison is field-by-field over what is
    actually checked rather than dict equality.
    """
    i8 = report["arms"]["published"]["invariant_8"]
    assert i8["agrees"] is True
    assert i8["n_cases_compared"] == 100
    assert i8["n_mismatches"] == 0
    for field in ("total_cost", "mean_cost", "missed_escalations", "action_counts"):
        assert (i8["recomputed_test_aggregate"][field]
                == i8["committed_test_aggregate"][field]), field
    assert i8["recomputed_test_aggregate"]["total_cost"] == 86
    assert i8["recomputed_test_aggregate"]["mean_cost"] == 1.72

    for arm in ("rebaselined", "raw", "calibrated"):
        other = report["arms"][arm]["invariant_8"]
        assert other["checked_on"] == "the published arm only", arm
        assert "recalibration changed nothing" in other["why"], arm
        assert "n_mismatches" not in other, arm


def test_invariant_8_uses_v1s_legacy_tie_break(eb, report):
    assert eb.LEGACY_TIE_BREAK is True
    i8 = report["arms"]["published"]["invariant_8"]
    assert "legacy" in i8["tie_break"]


# --------------------------------------------------------------------------- #
# Question selection
# --------------------------------------------------------------------------- #

def test_q_null_is_excluded_from_the_oracle(eb):
    assert "q_null" not in eb.ORACLE_CANDIDATES
    assert len(eb.ORACLE_CANDIDATES) == 3


def test_q_null_is_still_priced_as_the_zero_information_reference(eb, cases):
    for c in cases:
        assert "q_null" in c["by_question"]
        assert c["oracle_question"] != "q_null"


def test_the_oracle_and_argmax_ig_do_not_always_agree(eb, report):
    """If they agreed everywhere, the ordering-fragility caveat would be moot."""
    qs = report["arms"]["published"]["question_selection"]
    n = qs["n_test_cases_where_oracle_and_argmax_ig_agree"]
    assert qs["n_test_cases"] == 50
    assert 0 < n < 50


# --------------------------------------------------------------------------- #
# Self-consistency, named as such
# --------------------------------------------------------------------------- #

def test_self_consistency_is_never_called_validation(eb, report):
    blob = json.dumps(report) + eb.render(report)
    assert "self-consistency" in blob
    for arm in eb.ARMS:
        sc = report["arms"][arm]["self_consistency"]
        assert "validation" not in sc["name"]
        assert sc["external_validation"] == (
            "none; the Limitations entry is the paper gate's")
    assert not re.search(r"\bvoi[ -]validation\b", blob, re.IGNORECASE)


def test_the_monte_carlo_agrees_with_the_exact_expectation(eb, report):
    for arm in eb.ARMS:
        sc = report["arms"][arm]["self_consistency"]
        assert sc["agrees_within_1pct"] is True, arm
        assert sc["seed"] == eb.SEED
        assert sc["n_draws"] == eb.N_DRAWS


def test_a_state_reachable_answer_with_no_belief_branch_raises(eb, cases):
    """Negative control on the zero-probability guard in `_realised_expected`."""
    bent = copy.deepcopy(cases[0])
    q = bent["oracle_question"]
    argmins = bent["by_question"][q]["posterior_argmin_by_answer"]
    argmins.clear()
    with pytest.raises(eb.BaselineError, match="no posterior to act on"):
        eb._realised_expected(bent, q)


# --------------------------------------------------------------------------- #
# Naming
# --------------------------------------------------------------------------- #

def test_no_forbidden_vocabulary(eb):
    text = (SCRIPT.read_text(encoding="utf-8")
            + COMMITTED_MD.read_text(encoding="utf-8")
            + COMMITTED_JSON.read_text(encoding="utf-8")).lower()
    for word in ("cohort", "deliverable", "arthryx", "whatsapp", "real estate",
                 "kk"):
        assert word not in text


def test_the_impossibility_claim_keeps_its_qualifier(eb, report):
    """G7's binding wording: never the unqualified form."""
    blob = (json.dumps(report) + eb.render(report)
            + PREREG.read_text(encoding="utf-8")).lower()
    assert "asking never helps" not in blob
    assert "yes/no collapsed" not in blob


def test_entropy_is_never_compared_to_cost(eb, report):
    """`H(b)` is in bits and `V(b)` is in cost points; tau is the only bridge."""
    units = report["definitions"]["units"].lower()
    assert "bits" in units
    assert "cost points" in units
    for arm in eb.ARMS:
        for row in report["arms"][arm]["threshold_sweep"]["thresholds"]:
            assert "tau_bits" in row
            assert "tau_cost" not in row


def test_the_rebaselined_arm_carries_no_claim(eb, report):
    assert "rebaselined" in eb.ARMS
    note = report["beliefs"]["rebaselined_carries_no_claim"].lower()
    assert "no sentence" in note
    assert "rests on it" in note
    assert "cache-drift" in note
