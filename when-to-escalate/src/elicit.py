"""
elicit.py — continuous `needs_human` scores from token logprobs.

Why this exists. v1's beliefs came back on a 0.1 grid, and the model never emits
0.5 or 0.6 at all: it jumps 0.4 to 0.7. That grid is the model's own output
granularity, not a rounding step in the harness, so re-running the same prompt
recovers nothing. But the highest-uncertainty region is exactly where a
calibration map and a value-of-information story have anything to say, and the
grid cannot represent it. Reading the token logprobs recovers a continuous value
from the same call.

Two elicitors, because it is not knowable in advance which one is better
calibrated and the choice is pre-registered rather than picked after the fact
(see decisions/v2-gate2-preregistration.md).

  A. `digit_expectation` — v1's own prompt, unchanged, with logprobs switched on.
     The expectation is taken over the alternative digit tokens at the decisive
     position of the `needs_human` value. Nothing about the elicitation changes,
     so the continuous score is strictly more information from an identical call,
     and the reproduction check below can prove the elicitation is identical.

     Resolution caveat, stated because it is easy to overclaim: when the value is
     written `0.2` the decisive position holds the first decimal digit, so what A
     measures is the model's spread *across the same 0.1 grid v1 was confined
     to*. That is the right instrument for "is the grid hiding a spread?", and it
     is not the same thing as unbounded resolution.

  B. `yes_no_probability` — a separate one-token Yes/No question, where
     P(Yes) normalised over the Yes/No pair *is* the score. This is a genuine
     probability of exactly the binary event the 0.23 threshold acts on and that
     ECE, cross-entropy and Brier score, and it has no grid at all. It is a
     different elicitation from v1's, which is a real cost: the anchor case's
     "0.30 before, X after" then spans two methods, and that confound has to be
     stated wherever the number appears.

What this module does NOT do. It does not touch `belief.py`, `providers/`, or
`data/belief_cache.json`. Those are what keep v1's reported 1.720 / 16 misses
reproducing, and a calibration result is worth nothing if the baseline it is
measured against moved underneath it. Readiness is not re-elicited either: it is
already stored as a three-vector per case, Gate 2 recalibrates `needs_human`
only, and leaving readiness byte-identical means any change downstream traces to
one quantity.

The cache stores the raw token payload, not just the derived score. Every score
here comes out of an extraction routine that has to guess at tokenisation, and
tokenisation is exactly the kind of thing that is wrong the first time. Keeping
the payload means a bug in extraction is fixed by recomputing offline rather than
by paying for the calls again.

Pure standard library on purpose. The environment that runs the test suite has no
numpy, and `experiments/voi_ceiling.py` already set the precedent that this
project's arithmetic is stdlib-only.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:  # package import
    from .belief import CaseContext, input_hash
    from .config import ConfigError, find_repo_root
    from .providers.prompt import SYSTEM_PROMPT, render_observation
except ImportError:  # run directly, or imported with src/ on sys.path
    from belief import CaseContext, input_hash  # type: ignore
    from config import ConfigError, find_repo_root  # type: ignore
    from providers.prompt import SYSTEM_PROMPT, render_observation  # type: ignore

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# --------------------------------------------------------------------------- #
# Identity of the two elicitors
# --------------------------------------------------------------------------- #

ELICITOR_A = "digit_expectation"
ELICITOR_B = "yes_no_probability"
ELICITORS = (ELICITOR_A, ELICITOR_B)

#: OpenAI caps `top_logprobs` at 20. Asking for the maximum costs nothing extra
#: and the alternatives are the entire measurement, so there is no reason to
#: economise here.
TOP_LOGPROBS = 20

#: Below this, the alternatives at the decisive position are mostly NOT numeric,
#: which means the position was misidentified or the model wrote the value in a
#: shape the extractor does not understand. Reported per case and counted in the
#: run summary; it is a health check on extraction, not a filter on data.
MIN_NUMERIC_MASS = 0.95

CACHE_SCHEMA_VERSION = 1
DEFAULT_LOGPROB_CACHE_PATH = "when-to-escalate/data/logprob_cache.json"


class ElicitationError(RuntimeError):
    """A score could not be derived. Carries the elicitor and case so a failure
    in the middle of a 200-call run says which call broke."""

    def __init__(self, elicitor: str, case_id: str, message: str) -> None:
        super().__init__(f"{elicitor}/{case_id}: {message}")
        self.elicitor = elicitor
        self.case_id = case_id


# --------------------------------------------------------------------------- #
# Elicitor B's prompt
#
# The criterion below is lifted VERBATIM out of v1's SYSTEM_PROMPT, including its
# original indentation, so that `NEEDS_HUMAN_CRITERION in SYSTEM_PROMPT` is a
# true statement a test can assert. That test is the whole point: it means the
# two elicitors cannot drift apart on what `needs_human` actually means, so a
# difference between their scores is a difference in response format and nothing
# else. The odd indentation inside the new prompt is the price of that guarantee
# and is deliberate.
# --------------------------------------------------------------------------- #

NEEDS_HUMAN_CRITERION = """message should be handled by a human rather than an automated agent. Raise it for:
   legal or contractual questions, complaints or dissatisfaction, negotiation, sensitive
   or emotional content, or anything where a wrong automated answer could cause real harm."""

YES_NO_SYSTEM_PROMPT = f"""You are a lead-qualification analyst for an inbound sales channel.
You read ONE inbound message from a prospective customer and answer one question.

Question: should this message be handled by a human rather than an automated agent?

Judge it by exactly this criterion:
   {NEEDS_HUMAN_CRITERION}

This judgment is INDEPENDENT of how ready the prospect is to buy. A hot lead can
need a human; a cold lead can not need one. Do not tie the two together.

Answer with exactly one word: Yes or No. No punctuation, no explanation."""

#: Accepted spellings of the two answers. Compared after stripping whitespace and
#: lowercasing, so " Yes", "yes" and "YES" all count. Anything else is non-answer
#: mass and is reported rather than silently folded into one side.
YES_TOKENS = frozenset({"yes"})
NO_TOKENS = frozenset({"no"})


# --------------------------------------------------------------------------- #
# Environment. Read here rather than added to config.py, so Settings and the 337
# tests that exercise it are untouched.
# --------------------------------------------------------------------------- #

#: Mirrors config.py's vocabulary exactly. tests/test_elicit.py asserts the two
#: agree on every token, so they cannot drift into accepting different spellings
#: of "true" in the same repository.
_TRUE_TOKENS = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE_TOKENS = frozenset({"0", "false", "f", "no", "n", "off"})


def read_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    token = raw.strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    raise ConfigError(
        f"{name}={raw!r} is not a boolean. "
        f"Use one of: {', '.join(sorted(_TRUE_TOKENS | _FALSE_TOKENS))}."
    )


def logprob_cache_path() -> Path:
    """Absolute path to the logprob cache.

    Resolved against the repo root, never the working directory — the same bug
    config.py documents for the v1 cache, where running from two directories
    silently wrote two caches.
    """
    raw = os.environ.get("LOGPROB_CACHE_PATH", "").strip() or DEFAULT_LOGPROB_CACHE_PATH
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = find_repo_root() / path
    return path.resolve()


def cache_only() -> bool:
    """LOGPROB_CACHE_ONLY=true: serve from the cache, and make a miss an error.

    Same semantics as BELIEF_CACHE_ONLY, for the same reason — a reproduction that
    quietly mixed in fresh calls would no longer reproduce anything.
    """
    return read_bool_env("LOGPROB_CACHE_ONLY", False)


# --------------------------------------------------------------------------- #
# The token payload — a plain-dict shape, so fixtures are JSON and every scoring
# path is testable without the SDK.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class TokenRead:
    """One emitted token and the alternatives that were available at it."""

    token: str
    logprob: float
    top: tuple[tuple[str, float], ...] = field(default=())

    def probabilities(self) -> dict[str, float]:
        """Alternatives as probabilities, keyed by token text.

        Duplicate token texts are summed rather than overwritten. The API can
        return the same surface form twice for different underlying tokens, and
        dropping one of them would quietly lose probability mass.
        """
        import math

        out: dict[str, float] = {}
        for tok, lp in self.top:
            out[tok] = out.get(tok, 0.0) + math.exp(lp)
        if not out:
            out[self.token] = 1.0
        return out


def payload_from_sdk(response: Any) -> dict:
    """Flatten an OpenAI chat-completion response into a plain, JSON-safe dict.

    Kept separate from every scoring routine so that the SDK's object shape
    appears in exactly one place. Everything downstream consumes the dict, which
    is also what lands in the cache — so a stored payload can be rescored offline
    by code that has never seen the SDK.
    """
    choice = response.choices[0]
    tokens: list[dict] = []
    logprobs = getattr(choice, "logprobs", None)
    content = getattr(logprobs, "content", None) if logprobs is not None else None
    for item in content or []:
        top = [
            {"token": alt.token, "logprob": float(alt.logprob)}
            for alt in (getattr(item, "top_logprobs", None) or [])
        ]
        tokens.append({
            "token": item.token,
            "logprob": float(item.logprob),
            "top": top,
        })
    return {
        "text": choice.message.content or "",
        "tokens": tokens,
        "model": getattr(response, "model", None),
        "finish_reason": getattr(choice, "finish_reason", None),
    }


def token_reads(payload: dict) -> list[TokenRead]:
    """Payload dict -> TokenRead list. Tolerant of both dict and object `top`."""
    reads: list[TokenRead] = []
    for item in payload.get("tokens", []):
        top = tuple(
            (alt["token"], float(alt["logprob"]))
            for alt in item.get("top", [])
        )
        reads.append(TokenRead(token=item["token"], logprob=float(item["logprob"]), top=top))
    return reads


def token_spans(reads: list[TokenRead]) -> list[tuple[int, int]]:
    """Character span of each token in the concatenated text."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for read in reads:
        spans.append((pos, pos + len(read.token)))
        pos += len(read.token)
    return spans


# --------------------------------------------------------------------------- #
# Elicitor A — locating the needs_human value and reading its decisive position
# --------------------------------------------------------------------------- #

#: A JSON number. Deliberately permissive about the exponent form so that a
#: model writing 2e-1 is detected and reported as unparseable rather than
#: silently truncated to 2.
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_DIGITS = re.compile(r"\d+")


def find_value_span(text: str, key: str = "needs_human") -> tuple[int, int]:
    """Character span of `key`'s numeric value in a JSON object.

    A scanner rather than json.loads because the span in the ORIGINAL text is
    what maps back to tokens, and parsing throws that away.
    """
    marker = f'"{key}"'
    at = text.find(marker)
    if at < 0:
        raise ValueError(f"key {key!r} not found in payload text")
    cursor = at + len(marker)
    while cursor < len(text) and text[cursor] in " \t\r\n":
        cursor += 1
    if cursor >= len(text) or text[cursor] != ":":
        raise ValueError(f"no colon after key {key!r}")
    cursor += 1
    match = _NUMBER.search(text, cursor)
    if match is None or match.start() > cursor + 8:
        raise ValueError(f"no numeric value after key {key!r}")
    return match.start(), match.end()


def _covering_tokens(spans: list[tuple[int, int]], span: tuple[int, int]) -> list[int]:
    start, end = span
    return [i for i, (a, b) in enumerate(spans) if a < end and b > start]


@dataclass(frozen=True)
class DigitRead:
    """Where the decisive digit sits, and how the value was written."""

    index: int          # token index of the decisive position
    path: str           # "decimal" | "whole" | "integer"
    integer_part: str   # digits left of the point, "" when there is no point


def decisive_position(text: str, reads: list[TokenRead], span: tuple[int, int]) -> DigitRead:
    """Pick the token position whose alternatives carry the model's uncertainty.

    Three shapes, because tokenisers do not agree on numbers:

      "decimal"  0 . 2      the fraction digits are their own token, and that
                            token is the decisive one
      "whole"    0.2        the whole literal is one token, so the alternatives
                            are other whole literals
      "integer"  0          no decimal point at all

    Which shape applied is recorded per case rather than assumed, because an
    unexpected shape is the failure mode this routine exists to make visible.
    """
    spans = token_spans(reads)
    covering = _covering_tokens(spans, span)
    if not covering:
        raise ValueError("value span covers no token")

    value_text = text[span[0]:span[1]]
    dot = value_text.find(".")

    if dot < 0:
        return DigitRead(index=covering[0], path="integer", integer_part=value_text)

    dot_abs = span[0] + dot
    integer_part = value_text[:dot].lstrip("-")

    # The token holding the point: if it also holds the fraction digits, the
    # whole literal is one token and its alternatives are whole literals.
    for i in covering:
        a, b = spans[i]
        if a <= dot_abs < b:
            if b > dot_abs + 1:
                return DigitRead(index=i, path="whole", integer_part=integer_part)
            break

    # Otherwise the decisive position is whichever token holds the first
    # character after the point.
    for i in covering:
        a, b = spans[i]
        if a <= dot_abs + 1 < b:
            return DigitRead(index=i, path="decimal", integer_part=integer_part)

    raise ValueError("could not locate the digit position after the decimal point")


def _candidate_values(token: str, read: DigitRead) -> Optional[float]:
    """Numeric value implied by an alternative token at the decisive position.

    Leading digits only, so a token that arrived with trailing JSON punctuation
    ("2}") still reads as 2 rather than being discarded.
    """
    digits = _DIGITS.match(token.strip())
    if digits is None:
        return None
    body = digits.group(0)
    if read.path == "decimal":
        value = float(f"{read.integer_part or '0'}.{body}")
    else:
        try:
            value = float(token.strip())
        except ValueError:
            return None
    if not 0.0 <= value <= 1.0:
        return None
    return value


def score_digit_expectation(payload: dict, key: str = "needs_human") -> dict:
    """Continuous score for elicitor A, plus the diagnostics that judge it.

    Returns `score`, and enough context to tell a real spread from a collapse:
    `top1_prob` (how concentrated the model was), `mass_on_numeric` (whether the
    decisive position was identified correctly), and `path` (which tokenisation
    shape applied).
    """
    text = payload.get("text") or ""
    reads = token_reads(payload)
    if not reads:
        raise ValueError("payload carries no token logprobs")

    span = find_value_span(text, key)
    read = decisive_position(text, reads, span)
    at = reads[read.index]

    probabilities = at.probabilities()
    total = sum(probabilities.values())

    numeric: dict[float, float] = {}
    for token, prob in probabilities.items():
        value = _candidate_values(token, read)
        if value is None:
            continue
        numeric[value] = numeric.get(value, 0.0) + prob

    numeric_mass = sum(numeric.values())
    if not numeric:
        raise ValueError(
            f"no numeric alternative at the decisive position "
            f"(token {at.token!r}, path {read.path})"
        )

    score = sum(value * prob for value, prob in numeric.items()) / numeric_mass
    ranked = sorted(probabilities.items(), key=lambda kv: (-kv[1], kv[0]))

    return {
        "score": score,
        "path": read.path,
        "decisive_token": at.token,
        "decisive_index": read.index,
        "value_as_written": text[span[0]:span[1]],
        "top1_token": ranked[0][0],
        "top1_prob": ranked[0][1] / total if total else 1.0,
        "mass_on_numeric": numeric_mass / total if total else 0.0,
        "n_numeric_candidates": len(numeric),
        "n_alternatives": len(probabilities),
    }


# --------------------------------------------------------------------------- #
# Elicitor B — P(Yes) at the first content token
# --------------------------------------------------------------------------- #

def score_yes_no(payload: dict) -> dict:
    """Continuous score for elicitor B: P(Yes) normalised over the Yes/No pair.

    `mass_on_yes_no` is the diagnostic that matters. A low value means the model
    spent its probability somewhere other than the two answers it was asked for,
    and the ratio is then a ratio of two small numbers rather than a probability.

    The first *content* token is scored, not literally the first token. Models
    routinely emit a leading space or newline before the word, and reading
    position 0 blindly would find no Yes/No among its alternatives and raise on
    entirely ordinary output. Only whitespace-only tokens are skipped, so nothing
    meaningful can be stepped over.
    """
    reads = token_reads(payload)
    if not reads:
        raise ValueError("payload carries no token logprobs")

    at = None
    skipped = 0
    for read in reads:
        if read.token.strip() == "":
            skipped += 1
            continue
        at = read
        break
    if at is None:
        raise ValueError(
            f"every one of the {len(reads)} tokens is whitespace; the model "
            f"emitted no answer"
        )

    probabilities = at.probabilities()
    total = sum(probabilities.values())

    yes = no = 0.0
    for token, prob in probabilities.items():
        normalised = token.strip().lower()
        if normalised in YES_TOKENS:
            yes += prob
        elif normalised in NO_TOKENS:
            no += prob

    pair = yes + no
    if pair <= 0.0:
        raise ValueError(
            f"neither Yes nor No appeared among the alternatives at the first "
            f"content token (emitted {at.token!r})"
        )

    ranked = sorted(probabilities.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "score": yes / pair,
        "emitted_token": at.token,
        "leading_whitespace_tokens": skipped,
        "top1_token": ranked[0][0],
        "top1_prob": ranked[0][1] / total if total else 1.0,
        "mass_on_yes_no": pair / total if total else 0.0,
        "n_alternatives": len(probabilities),
    }


SCORERS = {
    ELICITOR_A: score_digit_expectation,
    ELICITOR_B: score_yes_no,
}


def score_payload(elicitor: str, payload: dict) -> dict:
    """Derive a score from a stored payload. The only route to a score.

    Nothing reads a score out of the cache directly. Scores are always recomputed
    from the payload, so fixing an extraction bug means re-running this function
    rather than re-running the calls.
    """
    try:
        scorer = SCORERS[elicitor]
    except KeyError:
        raise ValueError(
            f"unknown elicitor {elicitor!r}; expected one of {', '.join(ELICITORS)}"
        ) from None
    return scorer(payload)


# --------------------------------------------------------------------------- #
# The prompts each elicitor sends
# --------------------------------------------------------------------------- #

def system_prompt_for(elicitor: str) -> str:
    if elicitor == ELICITOR_A:
        return SYSTEM_PROMPT      # v1's, imported rather than copied
    if elicitor == ELICITOR_B:
        return YES_NO_SYSTEM_PROMPT
    raise ValueError(f"unknown elicitor {elicitor!r}")


def uses_json_mode(elicitor: str) -> bool:
    """Elicitor A must keep v1's response_format to stay the same call."""
    return elicitor == ELICITOR_A


def max_tokens_for(elicitor: str) -> Optional[int]:
    """B needs one word. A needs room for the whole JSON object."""
    return 3 if elicitor == ELICITOR_B else None


# --------------------------------------------------------------------------- #
# The cache
# --------------------------------------------------------------------------- #

def cache_key(elicitor: str, case_id: str) -> str:
    return f"{elicitor}:{case_id}"


def empty_cache() -> dict:
    return {"schema_version": CACHE_SCHEMA_VERSION, "entries": {}}


def load_cache(path: Path) -> dict:
    if not path.exists():
        return empty_cache()
    with open(path, "r", encoding="utf-8") as f:
        cache = json.load(f)
    version = cache.get("schema_version")
    if version != CACHE_SCHEMA_VERSION:
        raise ElicitationError(
            "cache", str(path),
            f"schema_version {version!r} is not the expected "
            f"{CACHE_SCHEMA_VERSION}. Refusing to read it, because silently "
            f"mixing schema versions is how a cache stops meaning one thing.",
        )
    cache.setdefault("entries", {})
    return cache


def save_cache(path: Path, cache: dict) -> None:
    """Atomic, sorted, stable. Same discipline as belief.py's cache writer.

    `sort_keys` is not cosmetic: it makes two runs over the same calls produce
    byte-identical files, which is what lets a determinism check be a diff.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def cache_entry(
    *,
    elicitor: str,
    case_id: str,
    model: str,
    observation_hash: str,
    prompt_hash: str,
    payload: dict,
    generated_at: str,
) -> dict:
    """One cache record. Carries the payload, not the score.

    `prompt_hash` is stored because the score is only comparable across cases if
    every case was asked the same question; a changed prompt has to be visible as
    a changed hash rather than inferred from a commit date.
    """
    return {
        "case_id": case_id,
        "elicitor": elicitor,
        "model": model,
        "observation_hash": observation_hash,
        "prompt_hash": prompt_hash,
        "generated_at": generated_at,
        "payload": payload,
    }


def prompt_hash(elicitor: str) -> str:
    import hashlib
    return hashlib.sha256(
        system_prompt_for(elicitor).encode("utf-8")
    ).hexdigest()[:16]


def observation_hash(message: str, context: Optional[CaseContext]) -> str:
    """v1's fingerprint function, imported rather than reimplemented.

    Using the same hash means a logprob entry and a v1 belief entry for the same
    case carry the same value, so the two caches can be joined and a drifted case
    is detectable across them.
    """
    return input_hash(message, context)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# The one function that touches the network
# --------------------------------------------------------------------------- #

def call_with_logprobs(
    *,
    elicitor: str,
    message: str,
    context: Optional[CaseContext],
    model: str,
    api_key: str,
) -> dict:
    """One chat completion with logprobs on. Returns a plain payload dict.

    Isolated so that nothing else in this module can make a paid call, and so the
    test suite can exercise every scoring path without a stub for this function.
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ElicitationError(
            elicitor, "-", "the `openai` package is not installed "
                           "(pip install -r requirements.txt)",
        ) from exc

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt_for(elicitor)},
            {"role": "user", "content": render_observation(message, context)},
        ],
        "temperature": 0,
        "logprobs": True,
        "top_logprobs": TOP_LOGPROBS,
    }
    if uses_json_mode(elicitor):
        kwargs["response_format"] = {"type": "json_object"}
    limit = max_tokens_for(elicitor)
    if limit is not None:
        kwargs["max_tokens"] = limit

    client = OpenAI(api_key=api_key)
    return payload_from_sdk(client.chat.completions.create(**kwargs))
