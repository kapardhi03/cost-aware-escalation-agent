"""
calibrate.py — calibration metrics, monotone maps, and the pre-registered rules
that choose between them.

Why the selection rules live in code rather than only in prose. Two choices in
Gate 2 could be made after seeing the results and dressed up afterwards as having
been the plan: which elicitor to believe, and which calibration map to fit. Both
are written here as functions, with their thresholds as module constants, and
`decisions/v2-gate2-preregistration.md` quotes this module. The rule is therefore
executed rather than remembered, and changing it is a diff.

Two things this module is careful about.

Clipping. Cross-entropy is infinite on a confident wrong answer, and v1 has a
case at exactly 0.00 with `needs_human` True. The clip bounds are not a new knob:
they are (0.02, 0.98), the same constants `Belief.clipped` already documents for
the same reason — an elicited 0.00 is not a probability, it is a refusal to
entertain the possibility.

Ordering. Resolution R7 prefers a map that preserves the ordering of the
continuous scores over one that minimises loss by merging them into blocks.
Isotonic regression merges; Platt scaling cannot. So the tie does not go to
whichever number is smaller — `select_map` prefers the strictly monotone map
unless isotonic beats it by more than a stated margin. That margin is the honest
form of "prefer, unless it costs too much".

Pure standard library. The environment that runs this project's test suite has no
numpy, and this is all small-n arithmetic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

# --------------------------------------------------------------------------- #
# Constants that the pre-registration fixes
# --------------------------------------------------------------------------- #

#: Same bounds as Belief.clipped, for the same reason. Applied before any
#: log-based quantity so a 0.00 score cannot make cross-entropy infinite.
CLIP_LOW = 0.02
CLIP_HIGH = 0.98

#: Equal-width bins for ECE and the reliability diagram. Ten is the convention
#: and with n=50 per split it already leaves bins nearly empty, which is a reason
#: to report bin counts alongside the number rather than to use more bins.
N_BINS = 10

#: Elicitor choice. Lower dev cross-entropy wins; within this margin the two are
#: treated as indistinguishable and ECE decides.
ELICITOR_TIE_MARGIN_BITS = 0.01

#: Map choice. Isotonic has to beat Platt by more than this on dev
#: cross-entropy to be preferred, because Platt preserves the score ordering that
#: R7 asks for and isotonic destroys it by construction.
MAP_MONOTONE_MARGIN_BITS = 0.02

#: Collapse test for elicitor A. v1's grid had 8 distinct `needs_human` values,
#: so an elicitor producing no more than that has recovered nothing, whatever its
#: cross-entropy says. A median top-1 probability at or above the threshold means
#: the model put essentially all its mass on one digit.
COLLAPSE_TOP1_MEDIAN = 0.99
COLLAPSE_MIN_DISTINCT = 9
SCORE_ROUNDING_DP = 3


def clip(p: float, low: float = CLIP_LOW, high: float = CLIP_HIGH) -> float:
    return min(high, max(low, p))


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

def _check(scores: Sequence[float], labels: Sequence[int]) -> int:
    if len(scores) != len(labels):
        raise ValueError(f"{len(scores)} scores against {len(labels)} labels")
    if not scores:
        raise ValueError("no cases")
    for y in labels:
        if y not in (0, 1, True, False):
            raise ValueError(f"label {y!r} is not binary")
    return len(scores)


def bin_index(p: float, n_bins: int = N_BINS) -> int:
    """Equal-width bin. 1.0 lands in the last bin rather than off the end."""
    return min(n_bins - 1, int(p * n_bins))


@dataclass(frozen=True)
class Bin:
    lo: float
    hi: float
    n: int
    mean_score: float      # confidence
    empirical_rate: float  # accuracy


def reliability_bins(
    scores: Sequence[float], labels: Sequence[int], n_bins: int = N_BINS,
) -> list[Bin]:
    """Per-bin count, mean predicted probability, and observed rate.

    Empty bins are kept in the list. Dropping them makes a reliability diagram
    look better than the data supports by hiding where there is no evidence.
    """
    _check(scores, labels)
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in zip(scores, labels):
        buckets[bin_index(p, n_bins)].append((p, int(y)))

    out: list[Bin] = []
    for i, bucket in enumerate(buckets):
        lo, hi = i / n_bins, (i + 1) / n_bins
        if not bucket:
            out.append(Bin(lo=lo, hi=hi, n=0, mean_score=float("nan"),
                           empirical_rate=float("nan")))
            continue
        n = len(bucket)
        out.append(Bin(
            lo=lo, hi=hi, n=n,
            mean_score=sum(p for p, _ in bucket) / n,
            empirical_rate=sum(y for _, y in bucket) / n,
        ))
    return out


def ece(scores: Sequence[float], labels: Sequence[int], n_bins: int = N_BINS) -> float:
    """Expected calibration error: count-weighted |observed rate - mean score|."""
    n = _check(scores, labels)
    total = 0.0
    for b in reliability_bins(scores, labels, n_bins):
        if b.n == 0:
            continue
        total += (b.n / n) * abs(b.empirical_rate - b.mean_score)
    return total


def cross_entropy_bits(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Mean binary cross-entropy in bits. The primary metric.

    Bits rather than nats so the number is readable against a reference: 1.0 bit
    is what a coin-flip predictor scores, and the label base rate's entropy is
    what a constant predictor scores.
    """
    _check(scores, labels)
    total = 0.0
    for p, y in zip(scores, labels):
        q = clip(float(p))
        total += -(math.log2(q) if int(y) == 1 else math.log2(1.0 - q))
    return total / len(scores)


def brier(scores: Sequence[float], labels: Sequence[int]) -> float:
    _check(scores, labels)
    return sum((float(p) - int(y)) ** 2 for p, y in zip(scores, labels)) / len(scores)


def base_rate(labels: Sequence[int]) -> float:
    return sum(int(y) for y in labels) / len(labels)


def entropy_bits(p: float) -> float:
    """Binary entropy in bits. 0 at the endpoints, by continuity."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def kl_bits(p: float, q: float) -> float:
    """KL(Bernoulli(p) || Bernoulli(q)) in bits, with q clipped."""
    q = clip(q)
    out = 0.0
    if p > 0.0:
        out += p * math.log2(p / q)
    if p < 1.0:
        out += (1.0 - p) * math.log2((1.0 - p) / (1.0 - q))
    return out


def ce_decomposition(
    scores: Sequence[float], labels: Sequence[int], n_bins: int = N_BINS,
) -> dict:
    """Split cross-entropy into an irreducible part and a miscalibration part.

    Within a bin, the label distribution has entropy no predictor can remove, and
    the gap between the bin's mean score and its observed rate is a KL divergence
    that a perfect recalibration would. That is the decomposition written in
    decisions/v2-definitions.md.

    Exact only if predictions are constant inside a bin, which they are not, so
    `residual` reports how far the identity misses. A large residual means the
    bins are too coarse to support reading the two parts separately.
    """
    n = _check(scores, labels)
    irreducible = miscalibration = 0.0
    for b in reliability_bins(scores, labels, n_bins):
        if b.n == 0:
            continue
        weight = b.n / n
        irreducible += weight * entropy_bits(b.empirical_rate)
        miscalibration += weight * kl_bits(b.empirical_rate, b.mean_score)
    measured = cross_entropy_bits(scores, labels)
    return {
        "cross_entropy_bits": measured,
        "irreducible_bits": irreducible,
        "miscalibration_bits": miscalibration,
        "binned_sum_bits": irreducible + miscalibration,
        "residual_bits": measured - (irreducible + miscalibration),
        "n_bins": n_bins,
    }


def all_metrics(
    scores: Sequence[float], labels: Sequence[int], n_bins: int = N_BINS,
) -> dict:
    """Every reported number for one (scores, labels) pair."""
    return {
        "n": len(scores),
        "base_rate": base_rate(labels),
        "cross_entropy_bits": cross_entropy_bits(scores, labels),
        "ece": ece(scores, labels, n_bins),
        "brier": brier(scores, labels),
        "base_rate_entropy_bits": entropy_bits(base_rate(labels)),
        "n_distinct_scores": len({round(float(p), SCORE_ROUNDING_DP) for p in scores}),
    }


# --------------------------------------------------------------------------- #
# Maps
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class IsotonicMap:
    """Step function from PAVA. Weakly monotone, and it merges ties by design.

    `knots` are (x, y) at the left edge of each block, x strictly increasing.
    Prediction interpolates linearly between knots and is flat outside them —
    flat rather than extrapolated, because an isotonic fit carries no information
    about a region it never saw and inventing a slope there would be fabrication.
    """

    knots: tuple[tuple[float, float], ...]
    name: str = "isotonic"
    strictly_monotone: bool = False

    def predict(self, x: float) -> float:
        xs = self.knots
        if x <= xs[0][0]:
            return xs[0][1]
        if x >= xs[-1][0]:
            return xs[-1][1]
        for (x0, y0), (x1, y1) in zip(xs, xs[1:]):
            if x0 <= x <= x1:
                if x1 == x0:
                    return y1
                t = (x - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
        return xs[-1][1]  # pragma: no cover - covered by the bounds above

    def to_dict(self) -> dict:
        return {"name": self.name, "strictly_monotone": self.strictly_monotone,
                "knots": [[x, y] for x, y in self.knots]}


@dataclass(frozen=True)
class PlattMap:
    """p = sigmoid(a * logit(clip(x)) + b). Strictly monotone whenever a > 0.

    Temperature scaling is the b = 0 special case; the two-parameter form is
    fitted because an intercept costs one number and corrects a base-rate offset
    that temperature alone cannot.
    """

    a: float
    b: float
    name: str = "platt"
    strictly_monotone: bool = True

    def predict(self, x: float) -> float:
        z = self.a * _logit(clip(float(x))) + self.b
        return _sigmoid(z)

    def to_dict(self) -> dict:
        return {"name": self.name, "strictly_monotone": self.strictly_monotone,
                "a": self.a, "b": self.b}


class IdentityMap:
    """The raw scores, unmapped. The thing every fitted map has to beat."""

    name = "identity"
    strictly_monotone = True

    def predict(self, x: float) -> float:
        return float(x)

    def to_dict(self) -> dict:
        return {"name": self.name, "strictly_monotone": True}


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    # Branch to avoid overflow in exp for large |z|.
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def fit_isotonic(scores: Sequence[float], labels: Sequence[int]) -> IsotonicMap:
    """Pool-adjacent-violators. Returns the step function it produces.

    Ties in x are pooled before the sweep. Leaving them separate lets PAVA order
    equal scores arbitrarily, which would make the fit depend on input order —
    and with v1's 0.1 grid, ties are the common case rather than an edge case.
    """
    _check(scores, labels)
    pairs = sorted(zip((float(s) for s in scores), (int(y) for y in labels)),
                   key=lambda xy: xy[0])

    # Pool equal x into one weighted point.
    blocks: list[list[float]] = []   # [x, sum_y, weight]
    for x, y in pairs:
        if blocks and blocks[-1][0] == x:
            blocks[-1][1] += y
            blocks[-1][2] += 1.0
        else:
            blocks.append([x, float(y), 1.0])

    # PAVA: merge any block whose mean is below its predecessor's.
    merged: list[list[float]] = []
    for block in blocks:
        merged.append(block)
        while len(merged) >= 2 and (merged[-2][1] / merged[-2][2]) > (merged[-1][1] / merged[-1][2]):
            last = merged.pop()
            prev = merged.pop()
            merged.append([prev[0], prev[1] + last[1], prev[2] + last[2]])

    knots = tuple((b[0], b[1] / b[2]) for b in merged)
    return IsotonicMap(knots=knots)


class SeparableError(ValueError):
    """The labels are perfectly separable by score, so no logistic MLE exists.

    Raised rather than worked around. The usual remedy is an L2 prior on the
    coefficients, which keeps the fit finite — but a prior is a knob, and a knob
    chosen after seeing that the fit failed is exactly the kind of decision this
    gate pre-registers away. The caller drops Platt from the candidate set and
    reports the exclusion instead.
    """


def _separable(scores: Sequence[float], labels: Sequence[int]) -> bool:
    """Is there a threshold on score that splits the labels perfectly?

    Checked directly rather than inferred from a diverging Newton iteration,
    because the two failures need different messages: no spread in the scores is
    a broken elicitor, and perfect separation is a fit that has no answer.
    """
    pairs = sorted(zip((float(s) for s in scores), (int(y) for y in labels)),
                   key=lambda xy: xy[0])
    ys = [y for _, y in pairs]
    if len(set(ys)) < 2:
        return True  # one class only: any threshold separates
    # A tie in score with disagreeing labels makes separation impossible.
    total_pos = sum(ys)
    n = len(ys)
    seen_pos = 0
    for i in range(n - 1):
        seen_pos += ys[i]
        if pairs[i][0] == pairs[i + 1][0]:
            continue  # cannot cut between equal scores
        left_n = i + 1
        # Perfect split either way round.
        if (seen_pos == 0 and total_pos == n - left_n) or \
           (seen_pos == left_n and total_pos == seen_pos):
            return True
    return False


def fit_platt(
    scores: Sequence[float], labels: Sequence[int],
    *, max_iterations: int = 200, tolerance: float = 1e-10,
) -> PlattMap:
    """Two-parameter logistic fit by Newton-Raphson on the log-likelihood.

    Raises if the gradient has not been driven to zero, and raises
    `SeparableError` up front if the data admits no finite fit. A silently
    unconverged fit would be reported as a calibration map, which is worse than
    an error: the numbers would look like a result.
    """
    _check(scores, labels)
    if len({round(float(s), 12) for s in scores}) < 2:
        raise ValueError("Platt fit: every score is identical; the elicitor "
                         "produced no spread to calibrate")
    if _separable(scores, labels):
        raise SeparableError(
            "Platt fit: score perfectly separates the labels, so the maximum "
            "likelihood estimate diverges and no finite (a, b) exists"
        )

    xs = [_logit(clip(float(s))) for s in scores]
    ys = [float(int(y)) for y in labels]

    a, b = 1.0, 0.0
    g_a = g_b = float("inf")  # so the failure message below is defined at zero iterations
    for _ in range(max_iterations):
        g_a = g_b = 0.0
        h_aa = h_ab = h_bb = 0.0
        for x, y in zip(xs, ys):
            p = _sigmoid(a * x + b)
            residual = p - y
            g_a += residual * x
            g_b += residual
            w = p * (1.0 - p)
            h_aa += w * x * x
            h_ab += w * x
            h_bb += w

        if max(abs(g_a), abs(g_b)) < tolerance:
            break

        # Ridge term keeps the 2x2 solve well-posed against floating-point noise.
        # It is not a regulariser on the fit — separation is rejected above, so
        # this only guards the linear solve, never the estimate.
        ridge = 1e-12
        det = (h_aa + ridge) * (h_bb + ridge) - h_ab * h_ab
        if abs(det) < 1e-18:
            raise ValueError("Platt fit: Hessian is singular; scores carry no spread")
        step_a = ((h_bb + ridge) * g_a - h_ab * g_b) / det
        step_b = ((h_aa + ridge) * g_b - h_ab * g_a) / det
        a -= step_a
        b -= step_b
    else:
        raise ValueError(
            f"Platt fit did not converge in {max_iterations} Newton steps "
            f"(|grad| = {max(abs(g_a), abs(g_b)):.3e}); refusing to return it"
        )

    return PlattMap(a=a, b=b)


def apply_map(mapping, scores: Sequence[float]) -> list[float]:
    return [mapping.predict(float(s)) for s in scores]


def is_order_preserving(mapping, scores: Sequence[float]) -> bool:
    """Whether the map keeps every strict ordering present in the scores.

    The concrete form of R7's worry: isotonic can send two distinct scores to the
    same value, and a value-of-information calculation downstream reads the
    ordering, not just the level.
    """
    distinct = sorted({round(float(s), SCORE_ROUNDING_DP) for s in scores})
    mapped = [mapping.predict(s) for s in distinct]
    return all(b > a for a, b in zip(mapped, mapped[1:]))


# --------------------------------------------------------------------------- #
# The pre-registered selection rules
# --------------------------------------------------------------------------- #

PREREGISTRATION = {
    "selection_split": "dev",
    "primary_metric": "cross_entropy_bits",
    "elicitor_tie_break": "ece",
    "elicitor_tie_margin_bits": ELICITOR_TIE_MARGIN_BITS,
    "map_candidates": ["identity", "platt", "isotonic"],
    "map_monotone_margin_bits": MAP_MONOTONE_MARGIN_BITS,
    "clip": [CLIP_LOW, CLIP_HIGH],
    "n_bins": N_BINS,
    "collapse_top1_median": COLLAPSE_TOP1_MEDIAN,
    "collapse_min_distinct": COLLAPSE_MIN_DISTINCT,
    "score_rounding_dp": SCORE_ROUNDING_DP,
    "primary_test_metrics": ["cross_entropy_bits", "ece", "brier"],
    "secondary_test_metrics": ["mean_cost", "escalation_misses"],
    "secondary_caveat": (
        "The test split carries only 8 of v1's 16 escalation misses, so a change "
        "of one or two misses is not evidence. Mean cost and miss count are "
        "reported alongside the calibration metrics and are not the claim."
    ),
}


def median(values: Sequence[float]) -> float:
    ordered = sorted(float(v) for v in values)
    n = len(ordered)
    if n == 0:
        raise ValueError("median of nothing")
    mid = n // 2
    return ordered[mid] if n % 2 else 0.5 * (ordered[mid - 1] + ordered[mid])


def collapse_verdict(scores: Sequence[float], top1_probs: Sequence[float]) -> dict:
    """Did this elicitor actually recover a spread, or reproduce the grid?

    Disqualifying rather than merely reported. An elicitor whose scores sit on the
    same eight values v1 had, with all the mass on one token, has measured
    nothing — and it could still post a decent cross-entropy by accident, which is
    exactly why the check is separate from the metric.
    """
    n_distinct = len({round(float(s), SCORE_ROUNDING_DP) for s in scores})
    top1_median = median(top1_probs) if top1_probs else 1.0
    collapsed = (n_distinct < COLLAPSE_MIN_DISTINCT) and (top1_median >= COLLAPSE_TOP1_MEDIAN)
    return {
        "n_distinct_scores": n_distinct,
        "median_top1_prob": top1_median,
        "min_distinct_required": COLLAPSE_MIN_DISTINCT,
        "top1_median_threshold": COLLAPSE_TOP1_MEDIAN,
        "collapsed": collapsed,
    }


def select_elicitor(candidates: dict[str, dict]) -> dict:
    """Apply the pre-registered elicitor rule.

    `candidates` maps elicitor name to a dict carrying at least
    `cross_entropy_bits`, `ece`, and `collapse` (from `collapse_verdict`).

    Order of operations matters and is fixed here: collapse disqualifies first,
    then cross-entropy decides, and ECE only breaks a tie inside the margin. A
    collapsed elicitor cannot win on cross-entropy, because the question it
    answers is not "which number is smaller" but "did this measure anything".
    """
    if not candidates:
        raise ValueError("no elicitors to choose between")

    eligible = {k: v for k, v in candidates.items()
                if not v.get("collapse", {}).get("collapsed", False)}
    disqualified = sorted(set(candidates) - set(eligible))

    if not eligible:
        return {
            "chosen": None,
            "reason": "every elicitor collapsed onto the grid it was meant to escape",
            "disqualified": disqualified,
            "rule": "collapse check disqualifies before any metric is compared",
        }

    ranked = sorted(eligible.items(), key=lambda kv: kv[1]["cross_entropy_bits"])
    best_name, best = ranked[0]

    if len(ranked) == 1:
        reason = (f"only eligible elicitor; dev cross-entropy "
                  f"{best['cross_entropy_bits']:.4f} bits")
        tie_break_used = False
    else:
        runner_name, runner = ranked[1]
        gap = runner["cross_entropy_bits"] - best["cross_entropy_bits"]
        tie_break_used = gap <= ELICITOR_TIE_MARGIN_BITS
        if tie_break_used:
            by_ece = sorted(eligible.items(), key=lambda kv: kv[1]["ece"])
            best_name, best = by_ece[0]
            reason = (f"cross-entropy gap {gap:.4f} bits is within the "
                      f"{ELICITOR_TIE_MARGIN_BITS} margin, so ECE decided: "
                      f"{best['ece']:.4f}")
        else:
            reason = (f"lower dev cross-entropy by {gap:.4f} bits, outside the "
                      f"{ELICITOR_TIE_MARGIN_BITS} margin")

    return {
        "chosen": best_name,
        "reason": reason,
        "tie_break_used": tie_break_used,
        "disqualified": disqualified,
        "ranking": [name for name, _ in ranked],
        "rule": ("collapse disqualifies; then lowest dev cross-entropy in bits; "
                 f"ties within {ELICITOR_TIE_MARGIN_BITS} bits go to lower ECE"),
    }


def select_map(candidates: dict[str, dict]) -> dict:
    """Apply the pre-registered map rule, with R7's preference built in.

    `candidates` maps map name to a dict carrying `cross_entropy_bits` and
    `order_preserving`. The order-preserving map wins unless a merging map beats
    it by more than MAP_MONOTONE_MARGIN_BITS on dev cross-entropy.
    """
    if not candidates:
        raise ValueError("no maps to choose between")

    ranked = sorted(candidates.items(), key=lambda kv: kv[1]["cross_entropy_bits"])
    best_name, best = ranked[0]

    if best.get("order_preserving", False):
        return {
            "chosen": best_name,
            "reason": (f"lowest dev cross-entropy ({best['cross_entropy_bits']:.4f} "
                       f"bits) and it preserves the score ordering"),
            "override_applied": False,
            "ranking": [name for name, _ in ranked],
            "rule": _MAP_RULE,
        }

    preserving = [(n, m) for n, m in ranked if m.get("order_preserving", False)]
    if not preserving:
        return {
            "chosen": best_name,
            "reason": (f"lowest dev cross-entropy ({best['cross_entropy_bits']:.4f} "
                       f"bits); no candidate preserved the ordering, so R7's "
                       f"preference could not be applied"),
            "override_applied": False,
            "ranking": [name for name, _ in ranked],
            "rule": _MAP_RULE,
        }

    keep_name, keep = preserving[0]
    gap = keep["cross_entropy_bits"] - best["cross_entropy_bits"]
    if gap > MAP_MONOTONE_MARGIN_BITS:
        return {
            "chosen": best_name,
            "reason": (f"{best_name} beats the best order-preserving map "
                       f"({keep_name}) by {gap:.4f} bits, more than the "
                       f"{MAP_MONOTONE_MARGIN_BITS} margin, so the merge is worth it"),
            "override_applied": False,
            "ranking": [name for name, _ in ranked],
            "rule": _MAP_RULE,
        }

    return {
        "chosen": keep_name,
        "reason": (f"{best_name} is only {gap:.4f} bits better, within the "
                   f"{MAP_MONOTONE_MARGIN_BITS} margin, so R7's preference for an "
                   f"order-preserving map applies"),
        "override_applied": True,
        "ranking": [name for name, _ in ranked],
        "rule": _MAP_RULE,
    }


_MAP_RULE = (
    "lowest dev cross-entropy in bits, except that an order-preserving map is "
    f"kept unless a merging map beats it by more than {MAP_MONOTONE_MARGIN_BITS} "
    "bits (resolution R7)"
)
