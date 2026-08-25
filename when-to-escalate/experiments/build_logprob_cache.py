"""
build_logprob_cache.py — elicit continuous `needs_human` scores via token logprobs.

Usage
    python experiments/build_logprob_cache.py --dry-run   # offline, NOT reportable
    python experiments/build_logprob_cache.py             # live, needs OPENAI_API_KEY
    python experiments/build_logprob_cache.py --cache-only # reproduce from cache, no calls
    python experiments/build_logprob_cache.py --rescore    # recompute scores, no calls

This is the only script in Gate 2 that makes network calls, and it makes them
once. Everything downstream reads the cache it writes.

Why the raw payload is stored rather than the score. A score is an extraction
decision applied to a model response, and the extraction is the part most likely
to be wrong — it has to find which token carried the digit and which alternatives
the model considered. Storing the token/logprob payload means an extraction fix
costs a `--rescore`, not a re-run at real money. `--rescore` therefore has to
reproduce the committed scores byte-for-byte from the committed cache, and the
determinism check at the end of a run asserts exactly that.

Both elicitors run on every case, and the choice between them is made afterwards
by `calibrate.select_elicitor`, whose rule was committed before any call. Running
one, looking, then running the other is how a post-hoc choice gets told as a
plan.

The free verification. Elicitor A sends v1's own system prompt at temperature 0,
so the `needs_human` value written in its response text should be the number
already in `data/belief_cache.json`. It is the same prompt to the same model, and
nothing here is allowed to smooth a mismatch: drift is counted, listed per case,
and reported. A drift count above zero does not stop the run — it is a finding
about temperature-0 reproducibility, which is worth more reported than hidden.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import calibrate as calib            # noqa: E402
import config as config_mod          # noqa: E402
import elicit as elicit_mod          # noqa: E402

logger = logging.getLogger("build_logprob_cache")

CASES_PATH = PROJECT_ROOT / "data" / "cases.json"
BELIEF_CACHE_PATH = PROJECT_ROOT / "data" / "belief_cache.json"
RESULTS_DIR = PROJECT_ROOT / "results"

#: Save the cache every this many paid calls, and again in a `finally`. A full run
#: is 200 calls into a ~1.3 MB file; writing once at the end means a rate-limit
#: error at call 190 throws away 189 calls that were already paid for. Ten bounds
#: the loss to ten calls at the price of ~20 whole-file writes, which is nothing
#: next to the latency of the calls themselves. Cache hits do not trigger a save —
#: there is nothing new to persist.
CHECKPOINT_EVERY = 10


# --------------------------------------------------------------------------- #
# The offline stub
# --------------------------------------------------------------------------- #

#: Marker written into every stub payload. `reportable` is derived from the
#: absence of this marker across all rows, NOT from the --dry-run flag. Found the
#: hard way: `--rescore` pointed at the dry cache produced a fully-reportable
#: results/logprob-elicitation.json out of stub payloads, because the flag said
#: "not a dry run" while the data said otherwise. Provenance has to travel with
#: the payload, or a later invocation launders it.
STUB_MARKER = "offline_stub"


def _stub_payload(elicitor: str, case: dict) -> dict:
    """A payload shaped exactly like the SDK's, derived from the case.

    Not a mock of `call_with_logprobs` — a substitute for its return value, so
    every line downstream of the call runs unchanged in --dry-run: extraction,
    scoring, caching, metrics, map fitting, selection. The numbers are
    deterministic nonsense and the output is stamped NOT REPORTABLE.

    The three digit-extraction paths are cycled across cases on purpose, so a
    dry run exercises `decimal`, `whole` and `integer` rather than only whichever
    one the first case happens to hit.

    The lean is derived from the label but deliberately overlaps it: a stub whose
    score separates the labels perfectly makes the Platt fit diverge, so a dry
    run would only ever exercise the failure path and never the ordinary one. The
    overlap is a fixed function of the case id, not a random draw, so repeated
    dry runs stay byte-identical.
    """
    seed = sum(ord(ch) for ch in case["case_id"])
    base = 0.6 if case["labels"]["needs_human"] else 0.3
    # Deterministic +/-0.2 wobble, enough that the two label groups overlap.
    lean = min(0.9, max(0.1, base + ((seed % 5) - 2) / 10))

    if elicitor == elicit_mod.ELICITOR_B:
        p_yes = min(0.95, max(0.05, lean + ((seed % 7) - 3) / 100))
        return {
            "text": "Yes" if p_yes >= 0.5 else "No",
            "tokens": [{
                "token": "Yes" if p_yes >= 0.5 else "No",
                "logprob": _ln(max(p_yes, 1 - p_yes)),
                "top": [{"token": "Yes", "logprob": _ln(p_yes)},
                        {"token": "No", "logprob": _ln(1.0 - p_yes)}],
            }],
            "model": STUB_MARKER, "finish_reason": "stop",
        }

    # Elicitor A. Three shapes, one per case_id modulo 3.
    shape = seed % 3
    written = f"{lean:.1f}"
    text = ('{"hot": 0.1, "warm": 0.3, "cold": 0.6, '
            f'"needs_human": {written}}}')
    if shape == 0:      # decimal path: "0", ".", "2" as separate tokens
        tokens = _stub_json_tokens(text, written, split=True, lean=lean)
    elif shape == 1:    # whole path: "0.2" as one token
        tokens = _stub_json_tokens(text, written, split=False, lean=lean)
    else:               # integer path: no decimal point at all
        written = "1" if lean >= 0.5 else "0"
        text = ('{"hot": 0.1, "warm": 0.3, "cold": 0.6, '
                f'"needs_human": {written}}}')
        tokens = _stub_json_tokens(text, written, split=False, lean=lean,
                                   integer=True)
    return {"text": text, "tokens": tokens, "model": STUB_MARKER,
            "finish_reason": "stop"}


def _ln(p: float) -> float:
    import math
    return math.log(max(p, 1e-12))


def _stub_json_tokens(text: str, written: str, *, split: bool, lean: float,
                      integer: bool = False) -> list[dict]:
    """Tokenise `text` so the decisive digit sits where the scorer expects it.

    Everything except the decisive value is one token per character with a
    degenerate top-1, which is enough for the span-to-token mapping to be
    exercised without pretending to model a real tokeniser.
    """
    start = text.rindex(written)
    tokens: list[dict] = []

    def plain(chunk: str) -> None:
        tokens.append({"token": chunk, "logprob": 0.0,
                       "top": [{"token": chunk, "logprob": 0.0}]})

    for ch in text[:start]:
        plain(ch)

    if integer:
        alt = "0" if written == "1" else "1"
        tokens.append({"token": written, "logprob": _ln(0.8),
                       "top": [{"token": written, "logprob": _ln(0.8)},
                               {"token": alt, "logprob": _ln(0.2)}]})
    elif split:
        plain("0")
        plain(".")
        digit = written.split(".")[1]
        neighbours = _neighbour_digits(digit)
        tokens.append({"token": digit, "logprob": _ln(0.6),
                       "top": [{"token": digit, "logprob": _ln(0.6)}] +
                              [{"token": d, "logprob": _ln(0.2)} for d in neighbours]})
    else:
        alts = [f"{max(0.0, lean - 0.1):.1f}", f"{min(1.0, lean + 0.1):.1f}"]
        tokens.append({"token": written, "logprob": _ln(0.6),
                       "top": [{"token": written, "logprob": _ln(0.6)}] +
                              [{"token": a, "logprob": _ln(0.2)} for a in alts]})

    for ch in text[start + len(written):]:
        plain(ch)
    return tokens


def _neighbour_digits(digit: str) -> list[str]:
    d = int(digit)
    return [str(x) for x in (d - 1, d + 1) if 0 <= x <= 9]


# --------------------------------------------------------------------------- #
# Building the cache
# --------------------------------------------------------------------------- #

def build(cases, *, settings, cache_path: Path, dry_run: bool,
          cache_only: bool, rescore: bool) -> dict:
    """Fill the cache for every (elicitor, case) pair, then score from it.

    Four modes, one code path. A live run calls; --dry-run substitutes a payload;
    --cache-only and --rescore refuse to produce a payload at all and error on a
    miss. Scoring is identical in every mode because it reads the payload.
    """
    cache = elicit_mod.load_cache(cache_path)
    entries = cache["entries"]
    calls = hits = 0
    saved_at = 0
    rows = []

    def flush() -> None:
        """Persist whatever has been paid for so far.

        Called on a checkpoint and again in `finally`. `save_cache` writes to a
        temporary file and renames, so an interrupt mid-flush leaves the previous
        cache intact rather than a truncated one.
        """
        nonlocal saved_at
        if calls > saved_at:
            elicit_mod.save_cache(cache_path, cache)
            logger.info("wrote %s (%d calls, %d cache hits)",
                        cache_path, calls, hits)
            saved_at = calls

    try:
        for case in cases:
            ctx = elicit_mod.CaseContext.from_dict(case.get("context"))
            obs_hash = elicit_mod.observation_hash(case["message"], ctx)

            for elicitor in elicit_mod.ELICITORS:
                key = elicit_mod.cache_key(elicitor, case["case_id"])
                entry = entries.get(key)

                if entry is not None:
                    hits += 1
                    if entry["observation_hash"] != obs_hash:
                        raise elicit_mod.ElicitationError(
                            elicitor, case["case_id"],
                            f"cached observation_hash {entry['observation_hash']} does "
                            f"not match {obs_hash} recomputed from cases.json. The "
                            f"message or context changed after the call; the cached "
                            f"payload answers a different question.",
                        )
                    if entry["prompt_hash"] != elicit_mod.prompt_hash(elicitor):
                        raise elicit_mod.ElicitationError(
                            elicitor, case["case_id"],
                            f"cached prompt_hash {entry['prompt_hash']} does not match "
                            f"the current prompt. Scores across cases are only "
                            f"comparable if every case was asked the same question.",
                        )
                else:
                    if cache_only or rescore:
                        raise elicit_mod.ElicitationError(
                            elicitor, case["case_id"],
                            "not in the cache, and this mode makes no calls. Run "
                            "without --cache-only/--rescore, with a real key.",
                        )
                    payload = (_stub_payload(elicitor, case) if dry_run
                               else elicit_mod.call_with_logprobs(
                                   elicitor=elicitor, message=case["message"],
                                   context=ctx, model=settings.openai_model,
                                   api_key=settings.openai_api_key))
                    calls += 1
                    entry = elicit_mod.cache_entry(
                        elicitor=elicitor, case_id=case["case_id"],
                        model=payload.get("model") or settings.openai_model,
                        observation_hash=obs_hash,
                        prompt_hash=elicit_mod.prompt_hash(elicitor),
                        payload=payload, generated_at=elicit_mod.utc_now(),
                    )
                    entries[key] = entry
                    logger.info("called %s for %s (%d)", elicitor, case["case_id"], calls)
                    if calls - saved_at >= CHECKPOINT_EVERY:
                        flush()

                scored = elicit_mod.score_payload(elicitor, entry["payload"])
                rows.append({
                    "case_id": case["case_id"], "split": case["split"],
                    "archetype": case["archetype"], "variant": case["variant"],
                    "elicitor": elicitor,
                    "label_needs_human": bool(case["labels"]["needs_human"]),
                    "model": entry["model"],
                    "score": scored["score"],
                    "detail": {k: v for k, v in scored.items() if k != "score"},
                })
    finally:
        # Runs on a rate-limit error, a Ctrl-C, or a scoring bug found at case 190.
        # Without it the run discards every call already paid for, and the operator
        # has to pay for all of them again to get back to where the failure was.
        flush()

    return {"rows": rows, "calls": calls, "hits": hits, "cache": cache}


# --------------------------------------------------------------------------- #
# The free verification: does elicitor A reproduce v1's cached beliefs?
# --------------------------------------------------------------------------- #

def reproduction_check(rows, belief_cache_path: Path) -> dict:
    """Compare the `needs_human` A wrote in its text against v1's cached value.

    Not the logprob-weighted score — the value as literally written, which is
    what v1 parsed. A comparison against the expectation would confound "the
    model said something different" with "the expectation is not the written
    digit", and only the first is drift.
    """
    if not belief_cache_path.exists():
        return {"available": False,
                "reason": f"{belief_cache_path.name} is absent; nothing to compare"}

    v1 = json.loads(belief_cache_path.read_text(encoding="utf-8"))
    compared, matched, drifted, unparseable = 0, 0, [], []

    for row in rows:
        if row["elicitor"] != elicit_mod.ELICITOR_A:
            continue
        cached = v1.get(row["case_id"])
        if cached is None:
            continue
        raw = row["detail"].get("value_as_written")
        if raw is None:
            continue
        # `value_as_written` is the literal text slice, kept as text so a
        # malformed value stays visible instead of being coerced into a number.
        try:
            written = float(raw)
        except (TypeError, ValueError):
            unparseable.append({"case_id": row["case_id"], "as_written": raw})
            continue
        compared += 1
        before = float(cached["belief"]["needs_human"])
        if abs(written - before) < 1e-9:
            matched += 1
        else:
            drifted.append({"case_id": row["case_id"], "v1": before,
                            "reelicited": written})

    return {
        "available": True,
        "compared": compared,
        "matched": matched,
        "drifted": len(drifted),
        "unparseable": len(unparseable),
        "match_rate": round(matched / compared, 4) if compared else None,
        "drift_detail": drifted,
        "unparseable_detail": unparseable,
        "note": ("Elicitor A sends v1's system prompt at temperature 0, so the "
                 "written value should equal v1's cached belief. Any drift is "
                 "reported as measured; nothing is adjusted to hide it."),
    }


# --------------------------------------------------------------------------- #
# Metrics, maps, and the pre-registered choices
# --------------------------------------------------------------------------- #

def analyse(rows) -> dict:
    """Per-elicitor metrics on dev and test, then apply the pre-registered rules.

    The maps are fitted on `dev` and applied to `test`. Nothing in this function
    consults a test number before making a choice; `select_elicitor` and
    `select_map` are handed dev metrics only, and that is enforced by only
    computing the test side after both selections have returned.
    """
    by_elicitor: dict[str, dict] = {}

    for elicitor in elicit_mod.ELICITORS:
        subset = [r for r in rows if r["elicitor"] == elicitor]
        if not subset:
            continue
        dev = [r for r in subset if r["split"] == "dev"]
        test = [r for r in subset if r["split"] == "test"]

        dev_s = [r["score"] for r in dev]
        dev_y = [int(r["label_needs_human"]) for r in dev]
        top1 = [r["detail"].get("top1_prob", 1.0) for r in subset]

        by_elicitor[elicitor] = {
            "n": len(subset),
            "dev": calib.all_metrics(dev_s, dev_y),
            "test": calib.all_metrics([r["score"] for r in test],
                                      [int(r["label_needs_human"]) for r in test]),
            "cross_entropy_bits": calib.cross_entropy_bits(dev_s, dev_y),
            "ece": calib.ece(dev_s, dev_y),
            "collapse": calib.collapse_verdict([r["score"] for r in subset], top1),
        }

    elicitor_choice = calib.select_elicitor(by_elicitor)
    chosen = elicitor_choice["chosen"]
    if chosen is None:
        return {"per_elicitor": by_elicitor, "elicitor_choice": elicitor_choice,
                "map_choice": None, "calibration": None}

    subset = [r for r in rows if r["elicitor"] == chosen]
    dev = [r for r in subset if r["split"] == "dev"]
    test = [r for r in subset if r["split"] == "test"]
    dev_s = [r["score"] for r in dev]
    dev_y = [int(r["label_needs_human"]) for r in dev]
    test_s = [r["score"] for r in test]
    test_y = [int(r["label_needs_human"]) for r in test]

    maps = {"identity": calib.IdentityMap(),
            "isotonic": calib.fit_isotonic(dev_s, dev_y)}
    excluded: dict[str, str] = {}
    try:
        maps["platt"] = calib.fit_platt(dev_s, dev_y)
    except ValueError as exc:
        # Reported, not swallowed. A missing candidate changes which map the
        # pre-registered rule can choose, so the reason has to be in the output
        # rather than inferable only from the absence of a row.
        excluded["platt"] = str(exc)
        logger.warning("platt excluded: %s", exc)

    map_metrics = {}
    for name, mapping in maps.items():
        mapped_dev = calib.apply_map(mapping, dev_s)
        map_metrics[name] = {
            "cross_entropy_bits": calib.cross_entropy_bits(mapped_dev, dev_y),
            "ece": calib.ece(mapped_dev, dev_y),
            "brier": calib.brier(mapped_dev, dev_y),
            "order_preserving": calib.is_order_preserving(mapping, dev_s),
            "params": mapping.to_dict(),
        }

    map_choice = calib.select_map(map_metrics)
    mapping = maps[map_choice["chosen"]]

    mapped_test = calib.apply_map(mapping, test_s)
    return {
        "per_elicitor": by_elicitor,
        "elicitor_choice": elicitor_choice,
        "map_candidates_dev": map_metrics,
        "maps_excluded": excluded,
        "map_choice": map_choice,
        "calibration": {
            "fitted_on": "dev",
            "evaluated_on": "test",
            "map": mapping.to_dict(),
            "test_raw": calib.all_metrics(test_s, test_y),
            "test_calibrated": calib.all_metrics(mapped_test, test_y),
            "test_raw_decomposition": calib.ce_decomposition(test_s, test_y),
            "test_calibrated_decomposition": calib.ce_decomposition(mapped_test, test_y),
            "test_reliability_raw": [_bin_row(b) for b in
                                     calib.reliability_bins(test_s, test_y)],
            "test_reliability_calibrated": [_bin_row(b) for b in
                                            calib.reliability_bins(mapped_test, test_y)],
            "order_preserved_on_test": calib.is_order_preserving(mapping, test_s),
        },
        "recalibrated_scores": {
            r["case_id"]: {"raw": r["score"], "calibrated": mapping.predict(r["score"]),
                           "split": r["split"]}
            for r in subset
        },
    }


def _bin_row(b) -> dict:
    import math
    nan = float("nan")
    return {"lo": b.lo, "hi": b.hi, "n": b.n,
            "mean_score": None if (b.n == 0 or math.isnan(b.mean_score)) else round(b.mean_score, 4),
            "empirical_rate": None if (b.n == 0 or math.isnan(b.empirical_rate)) else round(b.empirical_rate, 4)}


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def render(report: dict) -> str:
    L = ["# Logprob elicitation — continuous `needs_human` scores", ""]
    if not report["reportable"]:
        L += [f"> **NOT REPORTABLE.** {report['stub_rows']} of "
              f"{len(report['rows'])} rows come from the offline stub, not a "
              f"model. They exist to prove every code path runs. Not for the paper.",
              ""]
    L += [f"Generated {report['generated_at']} · {report['n_cases']} cases · "
          f"{report['calls']} calls, {report['cache_hits']} cache hits", ""]

    a = report["analysis"]
    L += ["## Elicitors", "",
          "Cross-entropy, ECE and Brier are on `dev` — the selection split. "
          "Distinct scores and median top-1 are over all cases, because the "
          "collapse check is a property of the elicitor rather than of a split.",
          "",
          "| elicitor | n dev | dev CE (bits) | dev ECE | dev Brier | distinct scores | "
          "median top-1 | collapsed |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |"]
    for name, m in a["per_elicitor"].items():
        c = m["collapse"]
        L.append(f"| `{name}` | {m['dev']['n']} | {m['dev']['cross_entropy_bits']:.4f} | "
                 f"{m['dev']['ece']:.4f} | {m['dev']['brier']:.4f} | "
                 f"{c['n_distinct_scores']} | {c['median_top1_prob']:.4f} | "
                 f"{'YES' if c['collapsed'] else 'no'} |")
    ec = a["elicitor_choice"]
    L += ["", f"Chosen: **{ec['chosen']}** — {ec['reason']}",
          f"Rule (pre-registered): {ec['rule']}", ""]
    if ec.get("disqualified"):
        L += [f"Disqualified by the collapse check: "
              f"{', '.join('`' + d + '`' for d in ec['disqualified'])}", ""]

    if a.get("map_choice"):
        L += ["## Calibration maps, fitted on dev", "",
              "| map | dev CE (bits) | dev ECE | dev Brier | order-preserving |",
              "| --- | ---: | ---: | ---: | :---: |"]
        for name, m in a["map_candidates_dev"].items():
            L.append(f"| `{name}` | {m['cross_entropy_bits']:.4f} | {m['ece']:.4f} | "
                     f"{m['brier']:.4f} | {'yes' if m['order_preserving'] else 'no'} |")
        mc = a["map_choice"]
        L += ["", f"Chosen: **{mc['chosen']}** — {mc['reason']}",
              f"Rule (pre-registered): {mc['rule']}", ""]
        for name, why in (a.get("maps_excluded") or {}).items():
            L += [f"Candidate `{name}` could not be fitted and was excluded: {why}", ""]

        cal = a["calibration"]
        L += ["## Held-out result — fitted on dev, evaluated on test", "",
              "| metric | raw | calibrated |", "| --- | ---: | ---: |"]
        for label, key in (("cross-entropy (bits)", "cross_entropy_bits"),
                           ("ECE", "ece"), ("Brier", "brier")):
            L.append(f"| {label} | {cal['test_raw'][key]:.4f} | "
                     f"{cal['test_calibrated'][key]:.4f} |")
        L += ["",
              f"Test base rate {cal['test_raw']['base_rate']:.2f}, whose entropy is "
              f"{cal['test_raw']['base_rate_entropy_bits']:.4f} bits — the score a "
              f"constant predictor gets.",
              f"Score ordering preserved on test: "
              f"**{'yes' if cal['order_preserved_on_test'] else 'no'}**", ""]

    r = report["reproduction_check"]
    L += ["## Temperature-0 reproduction check (elicitor A against v1's cache)", ""]
    if not r["available"]:
        L += [f"Not run: {r['reason']}", ""]
    else:
        L += [f"{r['matched']}/{r['compared']} written values match v1's cached "
              f"belief exactly ({r['match_rate']:.2%}); {r['drifted']} drifted.", ""]
        if r.get("unparseable"):
            L += [f"{r['unparseable']} values could not be parsed as a number and "
                  f"are excluded from the comparison: "
                  f"{', '.join('`' + u['case_id'] + '`' for u in r['unparseable_detail'][:10])}",
                  ""]
        if r["drift_detail"]:
            L += ["| case | v1 | re-elicited |", "| --- | ---: | ---: |"]
            L += [f"| `{d['case_id']}` | {d['v1']} | {d['reelicited']} |"
                  for d in r["drift_detail"][:20]]
            L += [""]
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="offline stub payloads; output is marked NOT REPORTABLE "
                         "and written to a separate cache file")
    ap.add_argument("--cache-only", action="store_true",
                    help="serve every payload from the cache; a miss is an error")
    ap.add_argument("--rescore", action="store_true",
                    help="recompute scores from the cached payloads without "
                         "calling. Use after an extraction fix.")
    ap.add_argument("--limit", type=int, default=None,
                    help="first N cases only, for a cheap smoke test")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)-7s %(name)s: %(message)s")

    if args.dry_run and (args.cache_only or args.rescore):
        print("--dry-run cannot be combined with --cache-only or --rescore: one "
              "invents payloads, the others refuse to.", file=sys.stderr)
        return 1

    cache_path = elicit_mod.logprob_cache_path()
    if args.dry_run:
        # Same reasoning as run_policies.py's dry-run guard: stub payloads left in
        # the reportable cache would be served to a later live run, which would
        # then report stub numbers as model numbers.
        cache_path = PROJECT_ROOT / "data" / "logprob_cache_DRY.json"

    try:
        settings = config_mod.load_settings(reload=True)
    except config_mod.ConfigError as exc:
        if not (args.dry_run or args.cache_only or args.rescore):
            print(f"Configuration is not usable:\n\n  {exc}\n", file=sys.stderr)
            return 1
        settings = None

    live = not (args.dry_run or args.cache_only or args.rescore)
    if live and not (settings and settings.openai_api_key):
        print("A live run needs OPENAI_API_KEY. Use --dry-run for an offline "
              "check or --cache-only to reproduce from the committed cache.",
              file=sys.stderr)
        return 1

    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = data["cases"][: args.limit] if args.limit else data["cases"]
    logger.info("%d cases from %s; cache %s", len(cases), CASES_PATH.name, cache_path)

    try:
        built = build(cases, settings=settings, cache_path=cache_path,
                      dry_run=args.dry_run, cache_only=args.cache_only,
                      rescore=args.rescore)
    except elicit_mod.ElicitationError as exc:
        print(f"\nRun refused:\n\n  {exc}\n", file=sys.stderr)
        return 2

    rows = built["rows"]
    stubbed = [r["case_id"] for r in rows if r["model"] == STUB_MARKER]
    reportable = not stubbed
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reportable": reportable,
        "stub_rows": len(stubbed),
        "mode": ("dry-run" if args.dry_run else
                 "rescore" if args.rescore else
                 "cache-only" if args.cache_only else "live"),
        "n_cases": len(cases),
        "calls": built["calls"],
        "cache_hits": built["hits"],
        "cache_path": str(cache_path.relative_to(PROJECT_ROOT.parent)),
        "model_summary": ", ".join(f"{k}={v}" for k, v in
                                  sorted(Counter(r["model"] for r in rows).items())),
        "preregistration": calib.PREREGISTRATION,
        "prompt_hashes": {e: elicit_mod.prompt_hash(e) for e in elicit_mod.ELICITORS},
        "reproduction_check": reproduction_check(rows, BELIEF_CACHE_PATH),
        "analysis": analyse(rows),
        "rows": rows,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    stem = "logprob-elicitation" if reportable else "logprob-elicitation_DRY"
    (args.out / f"{stem}.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / f"{stem}.md").write_text(render(report), encoding="utf-8")

    print("\n" + render(report))
    print(f"\nwrote {args.out / (stem + '.json')}")
    print(f"wrote {args.out / (stem + '.md')}")

    if built["calls"]:
        print("\nNext: verify the cache reproduces these scores with no calls —\n"
              "  python experiments/build_logprob_cache.py --rescore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
