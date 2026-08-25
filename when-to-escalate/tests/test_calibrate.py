"""
Calibration metrics, monotone maps, and the pre-registered selection rules.

Every expected number here is derived in the test body, not copied from a run.
Two groups matter most.

The decomposition tests. Cross-entropy is claimed to split into an irreducible
conditional-entropy term and a KL miscalibration term. That identity is exact only
when predictions are constant inside a bin, so one test builds exactly that case
and asserts the residual is zero, and another builds a bin with varying
predictions and asserts the residual is not.

The selection-rule tests. `select_elicitor` and `select_map` are the executable
form of Gate 2's pre-registration. They are tested at their thresholds, in both
directions, because a rule that is only tested well inside its margins is a rule
whose boundary behaviour is still undecided when the real numbers arrive.
"""

from __future__ import annotations

import math

import pytest


# --------------------------------------------------------------------------- #
# Input guards
# --------------------------------------------------------------------------- #

def test_length_mismatch_is_refused(calibrate):
    with pytest.raises(ValueError, match="3 scores against 2 labels"):
        calibrate.cross_entropy_bits([0.1, 0.2, 0.3], [0, 1])


def test_empty_input_is_refused(calibrate):
    with pytest.raises(ValueError, match="no cases"):
        calibrate.ece([], [])


def test_non_binary_label_is_refused(calibrate):
    """A probability slipping in where a label goes would score silently."""
    with pytest.raises(ValueError, match="not binary"):
        calibrate.brier([0.5], [0.5])


def test_bools_are_accepted_as_labels(calibrate):
    """v1's `needs_human` labels are Python bools, not ints."""
    assert calibrate.base_rate([True, False, True, True]) == pytest.approx(0.75)
    assert calibrate.brier([1.0, 0.0], [True, False]) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Clipping
# --------------------------------------------------------------------------- #

def test_clip_bounds_match_beliefs(calibrate, belief):
    """Not a new knob: the same bounds v1's Belief.clipped already uses.

    If v1's constants move, this fails rather than letting two different clips
    coexist in one paper.
    """
    assert (calibrate.CLIP_LOW, calibrate.CLIP_HIGH) == (0.02, 0.98)
    raw = belief.Belief(readiness={"hot": 0.0, "warm": 0.0, "cold": 1.0},
                        needs_human=0.0)
    assert raw.clipped().needs_human == pytest.approx(calibrate.CLIP_LOW)
    high = belief.Belief(readiness={"hot": 1.0, "warm": 0.0, "cold": 0.0},
                         needs_human=1.0)
    assert high.clipped().needs_human == pytest.approx(calibrate.CLIP_HIGH)


def test_clip_leaves_the_interior_alone(calibrate):
    assert calibrate.clip(0.5) == 0.5
    assert calibrate.clip(-1.0) == calibrate.CLIP_LOW
    assert calibrate.clip(2.0) == calibrate.CLIP_HIGH


def test_confident_wrong_answer_is_finite_not_infinite(calibrate):
    """v1 has a case at needs_human 0.00 whose label is True.

    Unclipped, that single case makes the mean cross-entropy infinite and no
    comparison is possible. Clipped, it costs log2(1/0.02) bits.
    """
    assert calibrate.cross_entropy_bits([0.0], [1]) == pytest.approx(math.log2(50.0))
    assert calibrate.cross_entropy_bits([1.0], [0]) == pytest.approx(math.log2(50.0))


# --------------------------------------------------------------------------- #
# Binning
# --------------------------------------------------------------------------- #

def test_one_lands_in_the_last_bin(calibrate):
    """int(1.0 * 10) is 10, one past the end. Guarded, not left to chance."""
    assert calibrate.bin_index(1.0) == calibrate.N_BINS - 1
    assert calibrate.bin_index(0.0) == 0


@pytest.mark.parametrize("value,expected", [
    (0.0, 0), (0.1, 1), (0.2, 2), (0.3, 3), (0.4, 4),
    (0.5, 5), (0.6, 6), (0.7, 7), (0.8, 8), (0.9, 9),
])
def test_v1_grid_values_bin_where_they_read(calibrate, value, expected):
    """Every value v1's beliefs actually take, checked against float arithmetic.

    `int(x * 10)` is one rounding error away from off-by-one — 0.7 * 10 could
    plausibly have been 6.999... and put a whole bin's worth of cases in the wrong
    place. It does not on this platform, and this is the test that says so rather
    than the comment.
    """
    assert calibrate.bin_index(value) == expected


def test_reliability_bins_keep_the_empty_ones(calibrate):
    """Dropping empty bins hides where there is no evidence."""
    bins = calibrate.reliability_bins([0.15, 0.15, 0.95], [0, 1, 1])
    assert len(bins) == calibrate.N_BINS
    assert [b.n for b in bins] == [0, 2, 0, 0, 0, 0, 0, 0, 0, 1]
    assert math.isnan(bins[0].mean_score)
    assert math.isnan(bins[0].empirical_rate)


def test_reliability_bin_contents(calibrate):
    bins = calibrate.reliability_bins([0.12, 0.18, 0.9], [0, 1, 1])
    hot = bins[1]
    assert hot.n == 2
    assert (hot.lo, hot.hi) == (0.1, pytest.approx(0.2))
    assert hot.mean_score == pytest.approx(0.15)
    assert hot.empirical_rate == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# Metrics, hand-computed
# --------------------------------------------------------------------------- #

def test_ece_is_count_weighted(calibrate):
    """scores 0.1, 0.1, 0.3, 0.9 against labels 0, 1, 0, 1.

    bin 1: n=2, mean 0.1, rate 0.5 -> 0.4 * 2/4 = 0.20
    bin 3: n=1, mean 0.3, rate 0.0 -> 0.3 * 1/4 = 0.075
    bin 9: n=1, mean 0.9, rate 1.0 -> 0.1 * 1/4 = 0.025
    """
    assert calibrate.ece([0.1, 0.1, 0.3, 0.9], [0, 1, 0, 1]) == pytest.approx(0.30)


def test_ece_is_zero_for_a_perfectly_calibrated_bin(calibrate):
    """Half the 0.5s positive. ECE cannot see that the predictions are useless."""
    assert calibrate.ece([0.5] * 4, [1, 0, 1, 0]) == pytest.approx(0.0)


def test_cross_entropy_hand_computed(calibrate):
    expected = (-math.log2(0.9) - math.log2(0.8)) / 2
    assert calibrate.cross_entropy_bits([0.9, 0.2], [1, 0]) == pytest.approx(expected)


def test_coin_flip_predictor_scores_one_bit(calibrate):
    """The reference that makes bits readable."""
    assert calibrate.cross_entropy_bits([0.5] * 6, [1, 0, 1, 0, 1, 0]) == pytest.approx(1.0)


def test_constant_predictor_scores_the_base_rate_entropy(calibrate):
    """Predicting the base rate everywhere costs exactly H(base rate).

    This is the number every elicitor has to beat to have measured anything.
    """
    labels = [1] * 42 + [0] * 58
    rate = calibrate.base_rate(labels)
    assert rate == pytest.approx(0.42)
    assert calibrate.cross_entropy_bits([rate] * 100, labels) == pytest.approx(
        calibrate.entropy_bits(rate))


def test_brier_hand_computed(calibrate):
    assert calibrate.brier([0.9, 0.2], [1, 0]) == pytest.approx((0.01 + 0.04) / 2)


def test_brier_is_unclipped(calibrate):
    """Brier has no log, so a 0.0 prediction is scored as written.

    Deliberate: clipping it would make the two metrics disagree about what was
    predicted, and Brier's job here is to be the one metric the clip cannot move.
    """
    assert calibrate.brier([0.0], [1]) == pytest.approx(1.0)


def test_entropy_endpoints_and_peak(calibrate):
    assert calibrate.entropy_bits(0.5) == pytest.approx(1.0)
    assert calibrate.entropy_bits(0.0) == 0.0
    assert calibrate.entropy_bits(1.0) == 0.0
    assert calibrate.entropy_bits(-0.1) == 0.0


def test_kl_is_zero_only_when_equal(calibrate):
    assert calibrate.kl_bits(0.3, 0.3) == pytest.approx(0.0)
    assert calibrate.kl_bits(0.3, 0.4) > 0.0
    assert calibrate.kl_bits(0.4, 0.3) > 0.0


def test_kl_clips_the_second_argument(calibrate):
    """KL(p || 0) is infinite; clipping q keeps the decomposition finite."""
    assert math.isfinite(calibrate.kl_bits(1.0, 0.0))


def test_all_metrics_reports_every_field_the_report_reads(calibrate):
    out = calibrate.all_metrics([0.1, 0.2, 0.2, 0.9], [0, 0, 1, 1])
    assert set(out) == {
        "n", "base_rate", "cross_entropy_bits", "ece", "brier",
        "base_rate_entropy_bits", "n_distinct_scores",
    }
    assert out["n"] == 4
    # 0.2 appears twice; distinct scores counts values, not cases.
    assert out["n_distinct_scores"] == 3


# --------------------------------------------------------------------------- #
# The cross-entropy decomposition
# --------------------------------------------------------------------------- #

def test_decomposition_is_exact_when_predictions_are_constant_in_a_bin(calibrate):
    """Four cases all at 0.25, two positive.

    irreducible   = H(0.5) = 1 bit
    miscalibration = KL(0.5 || 0.25)
                   = 0.5*log2(0.5/0.25) + 0.5*log2(0.5/0.75)
    and the two must sum to the measured cross-entropy exactly.
    """
    out = calibrate.ce_decomposition([0.25] * 4, [1, 1, 0, 0])
    assert out["irreducible_bits"] == pytest.approx(1.0)
    expected_kl = 0.5 * math.log2(0.5 / 0.25) + 0.5 * math.log2(0.5 / 0.75)
    assert out["miscalibration_bits"] == pytest.approx(expected_kl)
    assert out["residual_bits"] == pytest.approx(0.0, abs=1e-12)
    assert out["binned_sum_bits"] == pytest.approx(out["cross_entropy_bits"])


def test_decomposition_residual_is_nonzero_when_predictions_vary_in_a_bin(calibrate):
    """The honest failure mode, asserted rather than described.

    Both scores land in bin 1 but differ, so the bin's mean stands in for two
    different predictions and the identity no longer holds. A reader who sees a
    large residual should stop reading the two parts separately.
    """
    out = calibrate.ce_decomposition([0.11, 0.19], [1, 0])
    assert abs(out["residual_bits"]) > 1e-6


def test_perfectly_calibrated_predictions_have_no_miscalibration_term(calibrate):
    out = calibrate.ce_decomposition([0.5] * 4, [1, 0, 1, 0])
    assert out["miscalibration_bits"] == pytest.approx(0.0)
    assert out["irreducible_bits"] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Isotonic regression
# --------------------------------------------------------------------------- #

def test_isotonic_leaves_monotone_data_alone(calibrate):
    """Means per distinct score, no merging, when they already ascend."""
    fit = calibrate.fit_isotonic([0.1, 0.2, 0.3], [0, 0, 1])
    assert fit.knots == ((0.1, 0.0), (0.2, 0.0), (0.3, 1.0))


def test_isotonic_merges_a_violation(calibrate):
    """0.1 -> 1, 0.2 -> 0 descends, so PAVA pools them into one block at 0.5."""
    fit = calibrate.fit_isotonic([0.1, 0.2], [1, 0])
    assert fit.knots == ((0.1, 0.5),)
    assert fit.predict(0.1) == pytest.approx(0.5)
    assert fit.predict(0.9) == pytest.approx(0.5)


def test_isotonic_pools_ties_before_the_sweep(calibrate):
    """v1's 0.1 grid makes tied scores the common case, not an edge case.

    x = 0.2 carries labels 0 and 1, so it must contribute one weighted point at
    0.5 rather than two points PAVA can order however the input happened to arrive.
    """
    fit = calibrate.fit_isotonic([0.2, 0.2, 0.8], [0, 1, 1])
    assert fit.knots == ((0.2, pytest.approx(0.5)), (0.8, 1.0))


def test_isotonic_does_not_depend_on_input_order(calibrate):
    """The property tie-pooling exists to guarantee."""
    scores = [0.2, 0.1, 0.2, 0.1, 0.3]
    labels = [1, 0, 0, 1, 1]
    forward = calibrate.fit_isotonic(scores, labels)
    reverse = calibrate.fit_isotonic(list(reversed(scores)), list(reversed(labels)))
    assert forward.knots == reverse.knots


def test_isotonic_output_never_decreases(calibrate):
    fit = calibrate.fit_isotonic(
        [0.05, 0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 0.95],
        [0, 1, 0, 0, 1, 0, 1, 1])
    xs = [i / 50 for i in range(51)]
    ys = [fit.predict(x) for x in xs]
    assert all(b >= a - 1e-12 for a, b in zip(ys, ys[1:]))


def test_isotonic_is_flat_outside_its_knots(calibrate):
    """No extrapolated slope where the fit saw nothing.

    Inventing one would put a number on a region with no evidence behind it.
    """
    fit = calibrate.fit_isotonic([0.3, 0.7], [0, 1])
    assert fit.predict(0.0) == pytest.approx(fit.predict(0.3))
    assert fit.predict(1.0) == pytest.approx(fit.predict(0.7))


def test_isotonic_interpolates_between_knots(calibrate):
    fit = calibrate.fit_isotonic([0.2, 0.4], [0, 1])
    assert fit.predict(0.3) == pytest.approx(0.5)


def test_isotonic_can_destroy_the_score_ordering(calibrate):
    """R7's concrete worry, demonstrated.

    0.1 and 0.2 both map to 0.0. Downstream, a value-of-information calculation
    reads the ordering of beliefs, not only their level, so a map that merges two
    distinct scores has thrown away something the theorem half of this project
    uses.
    """
    fit = calibrate.fit_isotonic([0.1, 0.2, 0.3], [0, 0, 1])
    assert fit.predict(0.1) == fit.predict(0.2)
    assert calibrate.is_order_preserving(fit, [0.1, 0.2, 0.3]) is False


def test_isotonic_flags_itself_as_not_strictly_monotone(calibrate):
    assert calibrate.fit_isotonic([0.1, 0.2], [0, 1]).strictly_monotone is False


# --------------------------------------------------------------------------- #
# Platt scaling
# --------------------------------------------------------------------------- #

NON_SEPARABLE_SCORES = [0.1, 0.2, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
NON_SEPARABLE_LABELS = [0, 1, 0, 0, 1, 0, 1, 1, 0, 1]


def test_platt_reaches_a_stationary_point(calibrate):
    """The defining property of the fit: both gradient components are zero.

    Recomputed here from the returned coefficients rather than trusted from the
    solver, so a solver that stopped early fails this even if it raised nothing.
    """
    fit = calibrate.fit_platt(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS)
    g_a = g_b = 0.0
    for s, y in zip(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS):
        x = calibrate._logit(calibrate.clip(s))
        residual = fit.predict(s) - y
        g_a += residual * x
        g_b += residual
    assert abs(g_a) < 1e-8
    assert abs(g_b) < 1e-8


def test_platt_does_not_lose_to_the_identity_it_contains(calibrate):
    """a = 1, b = 0 is the clipped identity, and it is inside the family.

    So the maximum-likelihood fit cannot score worse on the data it was fitted to.
    A fit that does has converged to the wrong place.
    """
    fit = calibrate.fit_platt(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS)
    mapped = calibrate.cross_entropy_bits(
        calibrate.apply_map(fit, NON_SEPARABLE_SCORES), NON_SEPARABLE_LABELS)
    raw = calibrate.cross_entropy_bits(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS)
    assert mapped <= raw + 1e-9


def test_platt_is_strictly_monotone(calibrate):
    fit = calibrate.fit_platt(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS)
    assert fit.a > 0
    assert fit.strictly_monotone is True
    assert calibrate.is_order_preserving(fit, NON_SEPARABLE_SCORES) is True


def test_platt_predictions_stay_in_the_unit_interval(calibrate):
    fit = calibrate.fit_platt(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS)
    for x in (0.0, 0.001, 0.5, 0.999, 1.0):
        assert 0.0 < fit.predict(x) < 1.0


def test_sigmoid_does_not_overflow(calibrate):
    """The large-|z| branch. math.exp(1000) raises OverflowError unguarded."""
    assert calibrate._sigmoid(1000.0) == pytest.approx(1.0)
    assert calibrate._sigmoid(-1000.0) == pytest.approx(0.0)


def test_separable_data_raises_rather_than_being_regularised(calibrate):
    """Perfect separation has no finite MLE, and no prior is added to hide that.

    A prior chosen after seeing the fit fail is a knob chosen after seeing the
    data, which is the thing this gate pre-registers away.
    """
    with pytest.raises(calibrate.SeparableError, match="diverges"):
        calibrate.fit_platt([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])


def test_reverse_separation_is_also_caught(calibrate):
    with pytest.raises(calibrate.SeparableError):
        calibrate.fit_platt([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0])


def test_single_class_is_reported_as_separable(calibrate):
    """Any threshold separates one class, and the fit diverges the same way."""
    assert calibrate._separable([0.1, 0.2, 0.3], [1, 1, 1]) is True
    with pytest.raises(calibrate.SeparableError):
        calibrate.fit_platt([0.1, 0.2, 0.3], [1, 1, 1])


def test_a_tie_with_disagreeing_labels_defeats_separation(calibrate):
    """No cut can be made between two equal scores, so the fit exists."""
    assert calibrate._separable([0.1, 0.2, 0.2, 0.3], [0, 1, 0, 1]) is False
    calibrate.fit_platt([0.1, 0.2, 0.2, 0.3], [0, 1, 0, 1])


def test_separable_error_is_a_value_error(calibrate):
    """So a caller that only catches ValueError still catches it."""
    assert issubclass(calibrate.SeparableError, ValueError)


def test_no_spread_gets_its_own_message(calibrate):
    """A broken elicitor and an unfittable dataset are different failures.

    Both would show up as a diverging Newton iteration, so they are distinguished
    before the solve rather than after it.
    """
    with pytest.raises(ValueError, match="no spread to calibrate"):
        calibrate.fit_platt([0.5] * 4, [0, 1, 0, 1])


def test_unconverged_fit_is_refused_not_returned(calibrate):
    """An unconverged fit reported as a calibration map is worse than an error:
    the numbers would look like a result."""
    with pytest.raises(ValueError, match="did not converge"):
        calibrate.fit_platt(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS,
                            max_iterations=0)


# --------------------------------------------------------------------------- #
# Maps, generally
# --------------------------------------------------------------------------- #

def test_identity_map_is_the_raw_score(calibrate):
    assert calibrate.IdentityMap().predict(0.37) == pytest.approx(0.37)
    assert calibrate.is_order_preserving(calibrate.IdentityMap(), [0.1, 0.2]) is True


def test_every_map_serialises_with_its_name_and_monotonicity(calibrate):
    """The report has to be able to say which map was used and whether it merged."""
    maps = [
        calibrate.IdentityMap(),
        calibrate.fit_isotonic([0.1, 0.2], [0, 1]),
        calibrate.fit_platt(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS),
    ]
    for mapping in maps:
        as_dict = mapping.to_dict()
        assert as_dict["name"] == mapping.name
        assert "strictly_monotone" in as_dict


def test_apply_map_preserves_length_and_order(calibrate):
    scores = [0.3, 0.1, 0.9]
    out = calibrate.apply_map(calibrate.IdentityMap(), scores)
    assert out == pytest.approx(scores)


def test_order_preservation_ignores_duplicate_scores(calibrate):
    """Two cases at the same score are not an ordering the map could break."""
    fit = calibrate.fit_platt(NON_SEPARABLE_SCORES, NON_SEPARABLE_LABELS)
    assert calibrate.is_order_preserving(fit, [0.2, 0.2, 0.2]) is True


# --------------------------------------------------------------------------- #
# median
# --------------------------------------------------------------------------- #

def test_median_odd_and_even(calibrate):
    assert calibrate.median([3, 1, 2]) == 2
    assert calibrate.median([1, 2, 3, 4]) == pytest.approx(2.5)


def test_median_of_nothing_raises(calibrate):
    with pytest.raises(ValueError, match="median of nothing"):
        calibrate.median([])


# --------------------------------------------------------------------------- #
# The collapse diagnostic
# --------------------------------------------------------------------------- #

V1_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.7, 0.8, 0.9]  # the 8 values v1 produced


def test_reproducing_v1s_grid_with_all_the_mass_on_one_token_is_collapse(calibrate):
    """The failure this gate exists to detect.

    An elicitor that lands on the same eight values, with the model putting
    essentially all its probability on a single digit, has recovered no continuous
    information whatever its cross-entropy says.
    """
    verdict = calibrate.collapse_verdict(V1_GRID, [0.999] * len(V1_GRID))
    assert verdict["collapsed"] is True
    assert verdict["n_distinct_scores"] == 8


def test_both_conditions_are_required(calibrate):
    """Few distinct values with spread mass is a coarse elicitor, not a collapsed
    one; many distinct values with concentrated mass is a confident one."""
    assert calibrate.collapse_verdict(V1_GRID, [0.6] * 8)["collapsed"] is False
    many = [i / 100 for i in range(30)]
    assert calibrate.collapse_verdict(many, [0.999] * 30)["collapsed"] is False


def test_collapse_thresholds_are_at_their_stated_boundaries(calibrate):
    """Nine distinct values clears the bar; the top-1 test triggers at exactly 0.99.

    Both boundaries are asserted because a threshold whose inclusivity is only
    implied by the source is a threshold that is still open when the data lands.
    """
    nine = [i / 10 for i in range(9)]
    assert len(nine) == calibrate.COLLAPSE_MIN_DISTINCT
    assert calibrate.collapse_verdict(nine, [1.0] * 9)["collapsed"] is False

    eight = nine[:8]
    at = calibrate.collapse_verdict(eight, [calibrate.COLLAPSE_TOP1_MEDIAN] * 8)
    assert at["collapsed"] is True
    just_below = calibrate.collapse_verdict(eight, [0.98] * 8)
    assert just_below["collapsed"] is False


def test_collapse_reports_the_thresholds_it_applied(calibrate):
    verdict = calibrate.collapse_verdict(V1_GRID, [0.999] * 8)
    assert verdict["min_distinct_required"] == calibrate.COLLAPSE_MIN_DISTINCT
    assert verdict["top1_median_threshold"] == calibrate.COLLAPSE_TOP1_MEDIAN


def test_collapse_uses_the_median_not_the_mean_top1(calibrate):
    """One diffuse token cannot rescue an otherwise concentrated elicitor."""
    top1 = [0.01] + [0.999] * 8
    assert calibrate.collapse_verdict(V1_GRID, top1)["collapsed"] is True


def test_absent_top1_probabilities_default_to_collapsed(calibrate):
    """Elicitor B reports no per-digit top-1, so the absence must not read as
    evidence of spread."""
    assert calibrate.collapse_verdict(V1_GRID, [])["median_top1_prob"] == 1.0


# --------------------------------------------------------------------------- #
# select_elicitor
# --------------------------------------------------------------------------- #

def _cand(ce, ece_value, collapsed=False):
    return {"cross_entropy_bits": ce, "ece": ece_value,
            "collapse": {"collapsed": collapsed}}


def test_collapse_disqualifies_before_any_metric_is_compared(calibrate):
    """The order of operations, asserted.

    A collapsed elicitor with far better cross-entropy still loses, because the
    question the collapse check answers is not which number is smaller.
    """
    out = calibrate.select_elicitor({
        "digit_expectation": _cand(0.10, 0.01, collapsed=True),
        "yes_no": _cand(0.90, 0.30),
    })
    assert out["chosen"] == "yes_no"
    assert out["disqualified"] == ["digit_expectation"]


def test_every_elicitor_collapsing_yields_no_choice(calibrate):
    """Reported as no result rather than resolved to the least-bad option."""
    out = calibrate.select_elicitor({
        "digit_expectation": _cand(0.10, 0.01, collapsed=True),
        "yes_no": _cand(0.20, 0.02, collapsed=True),
    })
    assert out["chosen"] is None
    assert out["disqualified"] == ["digit_expectation", "yes_no"]


def test_clear_cross_entropy_win_needs_no_tie_break(calibrate):
    out = calibrate.select_elicitor({
        "digit_expectation": _cand(0.60, 0.25),
        "yes_no": _cand(0.90, 0.02),
    })
    assert out["chosen"] == "digit_expectation"
    assert out["tie_break_used"] is False
    assert out["ranking"] == ["digit_expectation", "yes_no"]


def test_ece_decides_inside_the_margin(calibrate):
    """A 0.005-bit gap is not a result, so the better-calibrated one wins."""
    out = calibrate.select_elicitor({
        "digit_expectation": _cand(0.500, 0.20),
        "yes_no": _cand(0.505, 0.05),
    })
    assert out["chosen"] == "yes_no"
    assert out["tie_break_used"] is True


def test_a_gap_exactly_at_the_margin_counts_as_a_tie(calibrate):
    """`gap <= margin`, so the boundary falls on the tie side.

    The magnitudes are chosen so the subtraction is exact in binary floating
    point (0.02 is 0.01 doubled, and doubling is exact), which is the only way to
    land on the boundary at all. They are not meant to be plausible cross-entropy
    values — this is a test of the comparison, not of the data.
    """
    margin = calibrate.ELICITOR_TIE_MARGIN_BITS
    assert (2 * margin) - margin == margin, "boundary must be exactly reachable"
    out = calibrate.select_elicitor({
        "digit_expectation": _cand(margin, 0.20),
        "yes_no": _cand(2 * margin, 0.05),
    })
    assert out["tie_break_used"] is True
    assert out["chosen"] == "yes_no"


def test_a_gap_a_hair_above_the_margin_is_not_a_tie(calibrate):
    """0.51 - 0.50 is 0.010000000000000009, which is outside a 0.01 margin.

    Worth writing down: the boundary is measure-zero on real data, so in practice
    the rule always resolves strictly one way or the other, and a gap that reads
    as "exactly the margin" on the page will usually be just outside it. The rule
    is still deterministic — it just never sits on the fence.
    """
    out = calibrate.select_elicitor({
        "digit_expectation": _cand(0.50, 0.20),
        "yes_no": _cand(0.51, 0.05),
    })
    assert out["tie_break_used"] is False
    assert out["chosen"] == "digit_expectation"


def test_a_tie_break_can_confirm_the_cross_entropy_leader(calibrate):
    """Inside the margin and also better calibrated: the leader keeps the win."""
    out = calibrate.select_elicitor({
        "digit_expectation": _cand(0.500, 0.05),
        "yes_no": _cand(0.505, 0.20),
    })
    assert out["chosen"] == "digit_expectation"
    assert out["tie_break_used"] is True


def test_a_single_eligible_elicitor_is_chosen_without_a_comparison(calibrate):
    out = calibrate.select_elicitor({"yes_no": _cand(0.90, 0.30)})
    assert out["chosen"] == "yes_no"
    assert out["tie_break_used"] is False


def test_choosing_between_no_elicitors_raises(calibrate):
    with pytest.raises(ValueError, match="no elicitors"):
        calibrate.select_elicitor({})


def test_elicitor_rule_text_states_the_margin(calibrate):
    """The reason string is what the paper quotes, so it has to carry the number."""
    out = calibrate.select_elicitor({"yes_no": _cand(0.90, 0.30)})
    assert str(calibrate.ELICITOR_TIE_MARGIN_BITS) in out["rule"]


# --------------------------------------------------------------------------- #
# select_map
# --------------------------------------------------------------------------- #

def _map_cand(ce, order_preserving):
    return {"cross_entropy_bits": ce, "order_preserving": order_preserving}


def test_an_order_preserving_winner_needs_no_override(calibrate):
    out = calibrate.select_map({
        "identity": _map_cand(0.90, True),
        "platt": _map_cand(0.70, True),
        "isotonic": _map_cand(0.80, False),
    })
    assert out["chosen"] == "platt"
    assert out["override_applied"] is False


def test_r7_keeps_the_monotone_map_inside_the_margin(calibrate):
    """Isotonic wins on loss by 0.01 bits, which is not worth losing the ordering."""
    out = calibrate.select_map({
        "platt": _map_cand(0.71, True),
        "isotonic": _map_cand(0.70, False),
    })
    assert out["chosen"] == "platt"
    assert out["override_applied"] is True
    assert "R7" in out["reason"]


def test_a_large_enough_gap_buys_the_merge(calibrate):
    """R7 is a preference, not a prohibition. 0.05 bits is worth the merge."""
    out = calibrate.select_map({
        "platt": _map_cand(0.75, True),
        "isotonic": _map_cand(0.70, False),
    })
    assert out["chosen"] == "isotonic"
    assert out["override_applied"] is False


def test_a_map_gap_exactly_at_the_margin_keeps_the_monotone_map(calibrate):
    """`gap > margin` buys the merge, so the boundary keeps the ordering.

    Same exactness trick as the elicitor boundary test: 0.04 - 0.02 is exact in
    binary, so the comparison genuinely runs at the boundary rather than a hair
    off it.
    """
    margin = calibrate.MAP_MONOTONE_MARGIN_BITS
    assert (2 * margin) - margin == margin, "boundary must be exactly reachable"
    out = calibrate.select_map({
        "platt": _map_cand(2 * margin, True),
        "isotonic": _map_cand(margin, False),
    })
    assert out["chosen"] == "platt"
    assert out["override_applied"] is True


def test_no_order_preserving_candidate_says_so(calibrate):
    """Platt can be excluded by separation, leaving nothing to prefer.

    Reported explicitly, because "isotonic was chosen" and "isotonic was the only
    thing left" are different facts.
    """
    out = calibrate.select_map({"isotonic": _map_cand(0.70, False)})
    assert out["chosen"] == "isotonic"
    assert out["override_applied"] is False
    assert "could not be applied" in out["reason"]


def test_choosing_between_no_maps_raises(calibrate):
    with pytest.raises(ValueError, match="no maps"):
        calibrate.select_map({})


def test_map_rule_text_states_the_margin_and_its_source(calibrate):
    out = calibrate.select_map({"identity": _map_cand(0.9, True)})
    assert str(calibrate.MAP_MONOTONE_MARGIN_BITS) in out["rule"]
    assert "R7" in out["rule"]


# --------------------------------------------------------------------------- #
# The pre-registration block
# --------------------------------------------------------------------------- #

def test_preregistration_matches_the_constants_it_reports(calibrate):
    """The record and the executed rule cannot drift apart silently.

    decisions/v2-gate2-preregistration.md quotes PREREGISTRATION, so if a constant
    moves without the block moving with it, the written record becomes false. This
    test is the link between the two.
    """
    pre = calibrate.PREREGISTRATION
    assert pre["clip"] == [calibrate.CLIP_LOW, calibrate.CLIP_HIGH]
    assert pre["n_bins"] == calibrate.N_BINS
    assert pre["elicitor_tie_margin_bits"] == calibrate.ELICITOR_TIE_MARGIN_BITS
    assert pre["map_monotone_margin_bits"] == calibrate.MAP_MONOTONE_MARGIN_BITS
    assert pre["collapse_top1_median"] == calibrate.COLLAPSE_TOP1_MEDIAN
    assert pre["collapse_min_distinct"] == calibrate.COLLAPSE_MIN_DISTINCT
    assert pre["score_rounding_dp"] == calibrate.SCORE_ROUNDING_DP


def test_selection_happens_on_dev_only(calibrate):
    """The whole point of the split. Written down where the rule is executed."""
    assert calibrate.PREREGISTRATION["selection_split"] == "dev"


def test_primary_metric_is_cross_entropy_and_misses_are_secondary(calibrate):
    """R5: the test split carries only 8 of 16 misses, so misses are not the claim."""
    pre = calibrate.PREREGISTRATION
    assert pre["primary_metric"] == "cross_entropy_bits"
    assert pre["primary_test_metrics"] == ["cross_entropy_bits", "ece", "brier"]
    assert pre["secondary_test_metrics"] == ["mean_cost", "escalation_misses"]
    assert "8 of v1's 16" in pre["secondary_caveat"]


def test_preregistration_is_json_serialisable(calibrate):
    """It is copied verbatim into results/logprob-elicitation.json."""
    import json
    assert json.loads(json.dumps(calibrate.PREREGISTRATION)) == calibrate.PREREGISTRATION
