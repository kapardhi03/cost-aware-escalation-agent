"""
make_figures.py — reliability diagram data for the `needs_human` marginal.

Three panels. Nothing here is transcribed by hand, and nothing is trusted: an
early version pasted the bin values in as literals, so the figure could silently
disagree with the results it claimed to plot, and the version after that read them
from the committed JSON without checking the JSON said what the caption claimed.
`--check` re-derives every plotted number from the per-case records and exits
non-zero on any mismatch.

The panels

1. `v1_needs_human` — the elicited marginal over all 100 cases, from
   results/run.json. This is the one with a render path.
2. `gate2_test_raw` — the raw logprob-derived score on the 50 test cases.
3. `gate2_test_calibrated` — the same 50 cases after the committed isotonic map.

Panels 2 and 3 have data and no render path. matplotlib is absent from the test
environment and this repo holds a pure-stdlib discipline, so a render path landed
here would ship untested; it lands at the paper gate
(decisions/v2-gate4-preregistration.md section 8).

What the panels must not share

An axis. All three use ten equal-width bins and the same index rule, so the bin
widths are in fact comparable — but the populations are not (100 cases against
50), the score sources are not (a one-decimal elicited marginal against a
continuous score), and run.json drops empty bins while the Gate 2 tables keep
them. Drawing them together would imply a comparison none of those differences
supports.

Three things a reliability diagram hides unless it is made to show them, each of
which changes how the figure should be read:

1. Bin sizes. v1's eight occupied bins hold between 4 and 35 cases. A diagram
   that draws them as identical markers invites the reader to weight a 4-case bin
   the same as a 35-case bin, which is exactly the misreading that produced the
   claim that under-confidence near the threshold explains all sixteen missed
   escalations.

2. Uncertainty. With n between 4 and 35, most of these bins are consistent with
   perfect calibration. Wilson intervals are drawn so the reader can see which
   deviations are real and which are sampling noise.

3. What a threshold can actually resolve — a different thing on each panel, so
   labelled separately rather than shaded identically:
   - v1: the elicited marginal only takes values at one decimal place, so no case
     takes a value in the open interval (0.2, 0.3), and every threshold in the
     half-open interval (0.2, 0.3] therefore decides identically. The two brackets
     differ and the difference is not cosmetic: 17 cases sit at exactly 0.3, so
     the value gap is open at the top, while a threshold at 0.3 still puts those
     17 on the escalate side and so is equivalent to 3/13. Both are re-derived and
     asserted separately below; writing one bracket for both claims is what the
     check caught. 3/13 is one arbitrary point inside the band, and a single line
     implies a precision the elicitation does not have.
   - `gate2_test_calibrated`: the committed map cannot emit a score below
     6/23 = 0.260870 at all, so [0, 6/23) is unreachable rather than merely
     unpopulated, and 3/13 = 0.230769 falls inside it. That is a statement about
     the map's range, not about this sample.
   - `gate2_test_raw`: no unreachable region. The raw score is continuous on
     (0, 1), so an empty bin there is a fact about 50 cases and nothing more.

Usage
    python paper/figures/make_figures.py            # verify, then render panel 1
    python paper/figures/make_figures.py --check    # verify only, no plotting library
"""

from __future__ import annotations

import argparse
import json
import math
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN_JSON = ROOT / "results" / "run.json"
ELICIT_JSON = ROOT / "results" / "logprob-elicitation.json"

THRESHOLD = 3 / 13          # where escalate_notify overtakes answer

# Committed reliability values are rounded to 4dp at the source; the aggregate
# metrics are not rounded at all. So the two comparisons need different rules.
ROUND_DP = 4
METRIC_TOL = 1e-12

PANELS = ("v1_needs_human", "gate2_test_raw", "gate2_test_calibrated")


@lru_cache(maxsize=None)
def _run() -> dict:
    return json.loads(RUN_JSON.read_text())


@lru_cache(maxsize=None)
def _elicit() -> dict:
    return json.loads(ELICIT_JSON.read_text())


def _bin_index(p: float, n_bins: int) -> int:
    """Equal-width bin; 1.0 lands in the last bin rather than off the end.

    Restated here rather than imported from `src.calibrate`, which is what wrote
    the committed tables. Re-deriving a number with the function that produced it
    checks nothing.
    """
    return min(n_bins - 1, int(p * n_bins))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for an observed frequency.

    Preferred over the normal approximation because several bins sit at or near an
    observed frequency of 0, where the normal interval extends below zero and is
    not usable.
    """
    if n == 0:
        return (0.0, 1.0)
    p, z2 = k / n, z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z / denom) * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5)
    return (max(0.0, centre - half), min(1.0, centre + half))


# --------------------------------------------------------------------------- #
# Panel 1: v1's elicited marginal, all 100 cases
# --------------------------------------------------------------------------- #

def v1_panel() -> dict:
    """Everything panel 1 draws, derived from run.json. No matplotlib needed.

    Kept separate from rendering so the numbers can be checked in an environment
    without a plotting library, and so the paper's caption can be verified against
    the same function that draws the figure.
    """
    payload = _run()
    cal = payload["summaries"]["all"]["calibration"]["needs_human"]

    bins = []
    for b in cal["bins"]:
        n = b["n"]
        k = round(b["observed_frequency"] * n)
        lo, hi = wilson(k, n)
        edge_lo = float(b["bin"].split("-")[0])
        edge_hi = float(b["bin"].split("-")[1])
        bins.append({
            "bin": b["bin"],
            "n": n,
            "predicted": b["mean_predicted"],
            "observed": b["observed_frequency"],
            "gap": b["gap"],
            "ci": [round(lo, 4), round(hi, 4)],
            "consistent_with_calibrated": lo <= b["mean_predicted"] <= hi,
            "contains_threshold": edge_lo <= THRESHOLD < edge_hi,
        })

    # Two intervals, not one. The values 0.2 and 0.3 are both attained, so the
    # gap in the *values* is open at both ends; the set of *thresholds* that
    # decide identically is closed at the top, because a threshold at 0.3 leaves
    # the 17 cases sitting there on the escalate side, same as 3/13 does.
    values = sorted({row["belief"]["needs_human"] for row in payload["rows"]})
    below = max((v for v in values if v <= THRESHOLD), default=THRESHOLD)
    above = min((v for v in values if v > THRESHOLD), default=THRESHOLD)

    # The diagram is drawn as separate segments wherever a bin is empty, so the
    # line never implies data in a range that has none.
    segments, current = [], []
    expected = None
    for b in bins:
        idx = int(round(b["predicted"] * 10))
        if expected is not None and idx != expected:
            segments.append(current)
            current = []
        current.append(b)
        expected = idx + 1
    if current:
        segments.append(current)

    n_at_top = sum(1 for r in payload["rows"]
                   if r["belief"]["needs_human"] == above)

    return {
        "panel": "v1_needs_human",
        "source": "results/run.json summaries.all.calibration.needs_human",
        "population": "all 100 cases",
        "score": "the elicited needs_human marginal, one decimal place",
        "n_bins": 10,
        "n_bins_occupied": len(bins),
        "empty_bins_dropped_at_source": True,
        "ece": cal["ece"],
        "n": cal["n"],
        "threshold": THRESHOLD,
        "distinct_values": values,
        "empty_value_interval": {
            "interval": [below, above],
            "closed": "(lo, hi)",
            "claim": "no case takes a value strictly inside",
            "why_open_at_the_top": f"{n_at_top} cases sit at exactly {above:g}",
        },
        "equivalent_threshold_interval": {
            "interval": [below, above],
            "closed": "(lo, hi]",
            "claim": "every threshold strictly above lo and up to and including hi "
                     "induces the same answer/escalate partition as 3/13",
            "why_closed_at_the_top": f"a threshold at {above:g} still leaves the "
                                     f"cases at {above:g} on the escalate side, "
                                     f"since the rule is b_h < t",
        },
        # Kept under the old key because the render label reads it. It is the
        # threshold interval, which is what the shaded band means.
        "indistinguishable_interval": [below, above],
        "bins": bins,
        "segments": [[b["bin"] for b in seg] for seg in segments],
        "_segments": segments,
        "empty_bins": [f"{i / 10:.1f}-{(i + 1) / 10:.1f}" for i in range(10)
                       if not any(int(round(b["predicted"] * 10)) == i for b in bins)],
        "renders": True,
    }


# --------------------------------------------------------------------------- #
# Panels 2 and 3: Gate 2's test-split scores, before and after the map
# --------------------------------------------------------------------------- #

def _test_pairs(which: str) -> list[tuple[str, float, int]]:
    """(case_id, score, label) for the 50 test cases, `which` in raw/calibrated.

    Labels come from run.json and scores from logprob-elicitation.json, so the
    join is across two artifacts and a case present in one but not the other would
    raise here rather than silently shrink the panel.
    """
    labels = {r["case_id"]: r["labels"]["needs_human"] for r in _run()["rows"]}
    scores = _elicit()["analysis"]["recalibrated_scores"]
    out = []
    for case_id, row in sorted(scores.items()):
        if row["split"] != "test":
            continue
        if case_id not in labels:
            raise KeyError(f"{case_id} is scored but carries no label in run.json")
        out.append((case_id, row[which], 1 if labels[case_id] else 0))
    return out


def _unreachable_region(which: str) -> dict:
    """What the panel's score simply cannot express, as opposed to did not.

    Only the calibrated panel has one. Conflating "no case landed here" with "no
    input could put a case here" is the thing this field exists to keep apart.
    """
    if which == "raw":
        return {
            "interval": None,
            "kind": "none",
            "cause": "the raw score is continuous on (0, 1); an empty bin here is "
                     "a fact about these 50 cases and nothing more",
        }
    floor = _elicit()["analysis"]["calibration"]["map"]["knots"][0][1]
    return {
        "interval": [0.0, floor],
        "closed": "[lo, hi)",
        "kind": "unreachable: the committed map cannot emit a score here at all",
        "cause": "PAVA sets the first block's level to its own positive rate, "
                 "6/23, and prediction clamps below the first knot",
        "floor_exact": "6/23",
        "floor": floor,
        "threshold_inside": floor > THRESHOLD,
    }


def gate2_panel(which: str) -> dict:
    """Panel 2 or 3, read from the committed Gate 2 reliability table."""
    cal = _elicit()["analysis"]["calibration"]
    committed = cal[f"test_reliability_{which}"]
    metrics = cal[f"test_{which}"]

    bins = []
    for b in committed:
        n = b["n"]
        if n == 0:
            bins.append({
                "bin": f"{b['lo']:.1f}-{b['hi']:.1f}", "n": 0,
                "predicted": None, "observed": None, "gap": None,
                "ci": None, "consistent_with_calibrated": None,
                "contains_threshold": b["lo"] <= THRESHOLD < b["hi"],
            })
            continue
        k = round(b["empirical_rate"] * n)
        lo, hi = wilson(k, n)
        bins.append({
            "bin": f"{b['lo']:.1f}-{b['hi']:.1f}",
            "n": n,
            "predicted": b["mean_score"],
            "observed": b["empirical_rate"],
            "gap": round(b["mean_score"] - b["empirical_rate"], 4),
            "ci": [round(lo, 4), round(hi, 4)],
            "consistent_with_calibrated": lo <= b["mean_score"] <= hi,
            "contains_threshold": b["lo"] <= THRESHOLD < b["hi"],
        })

    occupied = [b for b in bins if b["n"]]
    scores = [s for _, s, _ in _test_pairs(which)]
    return {
        "panel": f"gate2_test_{which}",
        "source": f"results/logprob-elicitation.json "
                  f"analysis.calibration.test_reliability_{which}",
        "population": "the 50 test cases; the map was fitted on dev",
        "score": f"the {which} needs_human score",
        "n_bins": _elicit()["preregistration"]["n_bins"],
        "n_bins_occupied": len(occupied),
        "empty_bins_dropped_at_source": False,
        "ece": metrics["ece"],
        "cross_entropy_bits": metrics["cross_entropy_bits"],
        "brier": metrics["brier"],
        "base_rate": metrics["base_rate"],
        "n": metrics["n"],
        "threshold": THRESHOLD,
        "n_cases_below_threshold": sum(1 for s in scores if s < THRESHOLD),
        "score_range": [min(scores), max(scores)],
        "unreachable_region": _unreachable_region(which),
        "bins": bins,
        "empty_bins": [b["bin"] for b in bins if not b["n"]],
        "renders": False,
        "render_deferred_to": "the paper gate; matplotlib is absent here and an "
                              "untested render path would ship unverified",
    }


def figure_data() -> dict:
    """All three panels, plus the reason they are not drawn on one axis."""
    v1 = v1_panel()
    raw = gate2_panel("raw")
    cal = gate2_panel("calibrated")
    return {
        "v1_needs_human": v1,
        "gate2_test_raw": raw,
        "gate2_test_calibrated": cal,
        "why_the_panels_are_not_one_figure": {
            "bin_width_is_shared": all(
                p["n_bins"] == 10 for p in (v1, raw, cal)),
            "populations": {p["panel"]: p["n"] for p in (v1, raw, cal)},
            "scores": {p["panel"]: p["score"] for p in (v1, raw, cal)},
            "empty_bins_dropped_at_source": {
                p["panel"]: p["empty_bins_dropped_at_source"]
                for p in (v1, raw, cal)},
            "note": "the bin widths do match — the ten equal-width bins and the "
                    "index rule are shared. What differs is the population, the "
                    "score source and whether empty bins survive to the artifact.",
        },
    }


# --------------------------------------------------------------------------- #
# The check: re-derive every plotted number from the per-case records
# --------------------------------------------------------------------------- #

def _ece(pairs: list[tuple[float, int]], n_bins: int) -> float:
    n = len(pairs)
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in pairs:
        buckets[_bin_index(p, n_bins)].append((p, y))
    total = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        observed = sum(y for _, y in bucket) / len(bucket)
        total += (len(bucket) / n) * abs(observed - mean_p)
    return total


def _check_v1(panel: dict) -> list[str]:
    """Re-bin the 100 elicited marginals and compare against the committed table."""
    bad = []
    pairs = [(r["belief"]["needs_human"], 1 if r["labels"]["needs_human"] else 0)
             for r in _run()["rows"]]
    if len(pairs) != panel["n"]:
        bad.append(f"v1: {len(pairs)} rows in run.json against n={panel['n']}")

    buckets: dict[int, list[tuple[float, int]]] = {}
    for p, y in pairs:
        buckets.setdefault(_bin_index(p, 10), []).append((p, y))

    if sorted(buckets) != [int(round(b["predicted"] * 10)) for b in panel["bins"]]:
        bad.append("v1: the set of occupied bins does not match the committed table")

    for b in panel["bins"]:
        idx = int(round(b["predicted"] * 10))
        bucket = buckets.get(idx, [])
        n = len(bucket)
        if n != b["n"]:
            bad.append(f"v1 bin {b['bin']}: recount {n} against committed {b['n']}")
            continue
        mean_p = sum(p for p, _ in bucket) / n
        k = sum(y for _, y in bucket)
        observed = k / n
        for name, got, want in (("mean_predicted", mean_p, b["predicted"]),
                                ("observed", observed, b["observed"]),
                                ("gap", mean_p - observed, b["gap"])):
            if round(got, ROUND_DP) != want:
                bad.append(f"v1 bin {b['bin']} {name}: {round(got, ROUND_DP)} "
                           f"against committed {want}")
        # The Wilson interval is drawn from a count recovered by un-rounding the
        # observed rate. If that recovery is ever wrong the error bars are wrong.
        if round(b["observed"] * n) != k:
            bad.append(f"v1 bin {b['bin']}: rounded rate recovers "
                       f"{round(b['observed'] * n)} positives, not {k}")

    got = _ece(pairs, 10)
    if round(got, ROUND_DP) != panel["ece"]:
        bad.append(f"v1 ece: {round(got, ROUND_DP)} against committed "
                   f"{panel['ece']}")

    # The shaded band carries two claims with two different brackets. Both are
    # checked, because the version before this one wrote the threshold bracket on
    # the value claim and nothing caught it.
    lo, hi = panel["empty_value_interval"]["interval"]
    inside_open = [p for p, _ in pairs if lo < p < hi]
    if inside_open:
        bad.append(f"v1: {len(inside_open)} cases strictly inside the value gap "
                   f"({lo:g}, {hi:g}), which is claimed empty")
    if not any(p == hi for p, _ in pairs):
        bad.append(f"v1: no case at {hi:g}, so the value gap should be closed "
                   f"there and the two brackets should not differ")
    if not lo < THRESHOLD <= hi:
        bad.append("v1: 3/13 is not inside the threshold band drawn around it")

    # The equivalence claim, verified as a partition identity rather than asserted
    # from the emptiness of the gap.
    def partition(t: float) -> frozenset:
        return frozenset(r["case_id"] for r in _run()["rows"]
                         if r["belief"]["needs_human"] < t)

    at_threshold = partition(THRESHOLD)
    if partition(hi) != at_threshold:
        bad.append(f"v1: a threshold at {hi:g} does not decide as 3/13 does, so "
                   f"the band cannot be closed at the top")
    if partition(lo) == at_threshold:
        bad.append(f"v1: a threshold at {lo:g} decides as 3/13 does, so the band "
                   f"is wider than drawn at the bottom")
    just_above = min((v for v in panel["distinct_values"] if v > hi), default=None)
    if just_above is not None and partition(just_above) == at_threshold:
        bad.append(f"v1: a threshold at {just_above:g} decides as 3/13 does, so "
                   f"the band is wider than drawn at the top")
    return bad


def _check_gate2(which: str, panel: dict) -> list[str]:
    """Re-bin the 50 test scores and recompute all three aggregate metrics."""
    bad = []
    triples = _test_pairs(which)
    pairs = [(s, y) for _, s, y in triples]
    n = len(pairs)
    if n != panel["n"]:
        bad.append(f"{which}: {n} test cases against committed n={panel['n']}")
        return bad

    n_bins = panel["n_bins"]
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in pairs:
        buckets[_bin_index(p, n_bins)].append((p, y))

    for bucket, b in zip(buckets, panel["bins"]):
        if len(bucket) != b["n"]:
            bad.append(f"{which} bin {b['bin']}: recount {len(bucket)} against "
                       f"committed {b['n']}")
            continue
        if not bucket:
            continue
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        k = sum(y for _, y in bucket)
        observed = k / len(bucket)
        for name, got, want in (("mean_score", mean_p, b["predicted"]),
                                ("empirical_rate", observed, b["observed"])):
            if round(got, ROUND_DP) != want:
                bad.append(f"{which} bin {b['bin']} {name}: "
                           f"{round(got, ROUND_DP)} against committed {want}")
        if round(b["observed"] * len(bucket)) != k:
            bad.append(f"{which} bin {b['bin']}: rounded rate recovers "
                       f"{round(b['observed'] * len(bucket))} positives, not {k}")

    lo_clip, hi_clip = _elicit()["preregistration"]["clip"]
    ce = -sum(y * math.log2(min(max(p, lo_clip), hi_clip))
              + (1 - y) * math.log2(1 - min(max(p, lo_clip), hi_clip))
              for p, y in pairs) / n
    metrics = (("ece", _ece(pairs, n_bins), panel["ece"]),
               ("cross_entropy_bits", ce, panel["cross_entropy_bits"]),
               ("brier", sum((p - y) ** 2 for p, y in pairs) / n, panel["brier"]),
               ("base_rate", sum(y for _, y in pairs) / n, panel["base_rate"]))
    for name, got, want in metrics:
        if abs(got - want) > METRIC_TOL:
            bad.append(f"{which} {name}: {got!r} against committed {want!r}, "
                       f"delta {abs(got - want):.3e} over {METRIC_TOL:.0e}")

    region = panel["unreachable_region"]
    if region["interval"] is not None:
        floor = region["floor"]
        below = [c for c, s, _ in triples if s < floor]
        if below:
            bad.append(f"{which}: {len(below)} scores below a floor claimed "
                       f"unreachable ({below[:3]})")
        if abs(floor - 6 / 23) > METRIC_TOL:
            bad.append(f"{which}: floor {floor!r} is not 6/23")
        if region["threshold_inside"] != (floor > THRESHOLD):
            bad.append(f"{which}: threshold_inside disagrees with the floor")
    return bad


def check(panels: dict) -> list[str]:
    """Every mismatch found, empty if the artifacts and the panels agree."""
    bad = _check_v1(panels["v1_needs_human"])
    for which in ("raw", "calibrated"):
        bad += _check_gate2(which, panels[f"gate2_test_{which}"])
    return bad


# --------------------------------------------------------------------------- #
# Rendering: panel 1 only
# --------------------------------------------------------------------------- #

def render(data: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 9, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7,
    })

    fig, ax = plt.subplots(figsize=(3.375, 2.9))

    ax.plot([0, 1], [0, 1], ls="--", lw=0.8, color="0.6",
            label="perfect calibration", zorder=1)

    lo, hi = data["indistinguishable_interval"]
    # Two brackets, deliberately. The band is the set of equivalent thresholds and
    # is closed at the top; the value gap it rests on is open at the top.
    ax.axvspan(lo, hi, color="0.88", zorder=0,
               label=f"thresholds equivalent to $3/13$: $({lo:g}, {hi:g}]$\n"
                     f"(no case takes a value in $({lo:g}, {hi:g})$)")
    ax.axvline(data["threshold"], ls="--", lw=1.0, color="black",
               label=r"threshold $3/13$", zorder=2)

    # Error bars first so the markers sit on top of them.
    for b in data["bins"]:
        ax.plot([b["predicted"]] * 2, b["ci"], lw=0.9, color="0.35",
                solid_capstyle="butt", zorder=3)

    for seg in data["_segments"]:
        ax.plot([b["predicted"] for b in seg], [b["observed"] for b in seg],
                lw=1.3, color="black", zorder=4)

    # Marker area proportional to bin count, so a 35-case bin cannot be read as
    # equal in weight to a 4-case bin.
    ax.scatter([b["predicted"] for b in data["bins"]],
               [b["observed"] for b in data["bins"]],
               s=[8 + 3.2 * b["n"] for b in data["bins"]],
               facecolor="white", edgecolor="black", lw=1.0, zorder=5,
               label="observed (area $\\propto$ bin count)")

    for b in data["bins"]:
        ax.annotate(f"{b['n']}", (b["predicted"], b["observed"]),
                    textcoords="offset points", xytext=(0, -3.2),
                    ha="center", va="center", fontsize=5.2, zorder=6)

    ax.set_xlim(-0.04, 1.04)
    ax.set_ylim(-0.04, 1.04)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel(r"Predicted $b_h$")
    ax.set_ylabel("Observed frequency")
    ax.grid(True, ls=":", lw=0.5, color="0.85")
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, handlelength=1.4,
              borderpad=0.2, labelspacing=0.35)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    fig.tight_layout(pad=0.2)
    for ext in ("pdf", "png"):
        out = HERE / f"reliability-needs-human.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight")
        print(f"wrote {out.relative_to(ROOT)}")


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def _print_bins(panel: dict) -> None:
    print(f"\n  {'bin':>9} {'n':>4} {'pred':>6} {'obs':>6} {'gap':>7} "
          f"{'95% CI':>16}  calibrated?  threshold?")
    for b in panel["bins"]:
        if not b["n"]:
            print(f"  {b['bin']:>9} {0:>4} {'—':>6} {'—':>6} {'—':>7} "
                  f"{'—':>16}   {'—':>9}"
                  f"   {'<-- contains 3/13' if b['contains_threshold'] else ''}")
            continue
        print(f"  {b['bin']:>9} {b['n']:>4} {b['predicted']:>6.3f} "
              f"{b['observed']:>6.3f} {b['gap']:>+7.3f} "
              f"[{b['ci'][0]:.3f}, {b['ci'][1]:.3f}]"
              f"   {'yes' if b['consistent_with_calibrated'] else 'no':>9}"
              f"   {'<-- contains 3/13' if b['contains_threshold'] else ''}")


def report(panels: dict) -> None:
    v1 = panels["v1_needs_human"]
    print(f"panel 1  {v1['panel']} — {v1['population']}, {v1['score']}")
    print(f"  ECE {v1['ece']} over n={v1['n']}; threshold 3/13 = "
          f"{v1['threshold']:.4f}")
    lo, hi = v1["empty_value_interval"]["interval"]
    print(f"  no case takes a value in ({lo:g}, {hi:g}) — open at the top, "
          f"{v1['empty_value_interval']['why_open_at_the_top']}")
    print(f"  every threshold in ({lo:g}, {hi:g}] decides identically — closed at "
          f"the top, verified as a partition identity, not inferred from the gap")
    print(f"  empty bins: {', '.join(v1['empty_bins']) or 'none'}")
    print(f"  segments drawn: {v1['segments']}")
    _print_bins(v1)

    for i, which in enumerate(("raw", "calibrated"), start=2):
        p = panels[f"gate2_test_{which}"]
        print(f"\npanel {i}  {p['panel']} — {p['population']}, {p['score']}")
        print(f"  ECE {p['ece']:.4f}, cross-entropy {p['cross_entropy_bits']:.4f} "
              f"bits, Brier {p['brier']:.4f}, base rate {p['base_rate']} "
              f"over n={p['n']}")
        print(f"  score range [{p['score_range'][0]:.4f}, "
              f"{p['score_range'][1]:.4f}]; {p['n_cases_below_threshold']} of "
              f"{p['n']} cases below 3/13")
        r = p["unreachable_region"]
        if r["interval"] is None:
            print(f"  unreachable region: none — {r['cause']}")
        else:
            print(f"  unreachable region [0, {r['floor_exact']}) = "
                  f"[0, {r['floor']:.6f}); 3/13 = {THRESHOLD:.6f} inside: "
                  f"{r['threshold_inside']}")
        print(f"  empty bins: {', '.join(p['empty_bins']) or 'none'}")
        print(f"  render path: deferred to {p['render_deferred_to']}")
        _print_bins(p)

    w = panels["why_the_panels_are_not_one_figure"]
    print(f"\nnot one figure: populations {w['populations']}; "
          f"empty bins kept {w['empty_bins_dropped_at_source']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the panels against the per-case records and exit; "
                         "no plotting library needed")
    args = ap.parse_args()

    panels = figure_data()
    report(panels)

    bad = check(panels)
    if bad:
        print(f"\nCHECK FAILED — {len(bad)} mismatch(es) against the per-case "
              f"records:")
        for line in bad:
            print(f"  - {line}")
        return 1
    print("\ncheck passed: every plotted number re-derived from the per-case "
          "records in results/run.json and results/logprob-elicitation.json")

    if args.check:
        return 0
    try:
        render(panels["v1_needs_human"])
    except ModuleNotFoundError as exc:
        print(f"\ncannot render ({exc}); the values above are still correct and "
              f"checked. Install matplotlib and re-run without --check.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
