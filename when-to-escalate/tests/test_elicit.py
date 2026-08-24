"""
Logprob elicitation: extraction, scoring, and cache integrity.

The scoring tests are the load-bearing ones. Every expected value here is
hand-computed in the test body rather than copied from a run, because a test that
asserts whatever the code produced today cannot catch the code being wrong today.
"""

from __future__ import annotations

import json
import math

import pytest


# --------------------------------------------------------------------------- #
# Payload builders — the SDK shape, made explicitly
# --------------------------------------------------------------------------- #

def tok(token, prob, top=None):
    """One token read. `top` is a {surface: probability} mapping."""
    return {
        "token": token,
        "logprob": math.log(prob),
        "top": [{"token": t, "logprob": math.log(p)} for t, p in (top or {token: prob}).items()],
    }


def json_payload(tokens, text, model="test-model"):
    return {"text": text, "tokens": tokens, "model": model, "finish_reason": "stop"}


def chars(s):
    """Degenerate one-char-per-token reads, for the parts we do not score."""
    return [tok(c, 1.0) for c in s]


# --------------------------------------------------------------------------- #
# The prompt guard
# --------------------------------------------------------------------------- #

def test_needs_human_criterion_is_verbatim_from_v1(elicit):
    """Elicitor B has to ask about the same thing v1's prompt asked about.

    If this drifts, B is measuring a different quantity than the labels describe
    and the two elicitors are no longer comparable. Asserted as a substring so a
    reworded v1 prompt fails here rather than silently changing what B means.
    """
    from providers.prompt import SYSTEM_PROMPT
    assert elicit.NEEDS_HUMAN_CRITERION in SYSTEM_PROMPT
    assert elicit.NEEDS_HUMAN_CRITERION in elicit.YES_NO_SYSTEM_PROMPT


def test_elicitor_a_sends_v1s_prompt_unchanged(elicit):
    from providers.prompt import SYSTEM_PROMPT
    assert elicit.system_prompt_for(elicit.ELICITOR_A) == SYSTEM_PROMPT


def test_prompt_hash_differs_between_elicitors(elicit):
    a = elicit.prompt_hash(elicit.ELICITOR_A)
    b = elicit.prompt_hash(elicit.ELICITOR_B)
    assert a != b
    assert len(a) == 16


def test_json_mode_only_for_a(elicit):
    assert elicit.uses_json_mode(elicit.ELICITOR_A) is True
    assert elicit.uses_json_mode(elicit.ELICITOR_B) is False


def test_unknown_elicitor_is_rejected(elicit):
    with pytest.raises(ValueError, match="unknown elicitor"):
        elicit.system_prompt_for("vibes")
    with pytest.raises(ValueError, match="unknown elicitor"):
        elicit.score_payload("vibes", json_payload(chars("x"), "x"))


# --------------------------------------------------------------------------- #
# Span location
# --------------------------------------------------------------------------- #

def test_find_value_span_locates_the_number(elicit):
    text = '{"hot": 0.1, "warm": 0.3, "cold": 0.6, "needs_human": 0.25}'
    lo, hi = elicit.find_value_span(text, "needs_human")
    assert text[lo:hi] == "0.25"


def test_find_value_span_is_not_confused_by_earlier_numbers(elicit):
    """`hot` also has a value; the scanner must key on the requested name."""
    text = '{"needs_human": 0.7, "hot": 0.1}'
    lo, hi = elicit.find_value_span(text, "hot")
    assert text[lo:hi] == "0.1"


def test_missing_key_raises(elicit):
    with pytest.raises(ValueError):
        elicit.find_value_span('{"hot": 0.1}', "needs_human")


# --------------------------------------------------------------------------- #
# Elicitor A — the three tokenisation paths
# --------------------------------------------------------------------------- #

def test_decimal_path_weights_fraction_digits(elicit):
    """`0` `.` `2` — the fraction digit owns its own token.

    Hand-computed: candidates 0.2 (0.55), 0.3 (0.30), 0.1 (0.10) carry 0.95 of
    the mass, and a non-numeric alternative carries 0.05. Normalising over the
    numeric mass only:
        (0.2*0.55 + 0.3*0.30 + 0.1*0.10) / 0.95 = 0.21 / 0.95
    """
    text = '{"needs_human": 0.2}'
    head = chars('{"needs_human": ')
    tokens = head + [tok("0", 1.0), tok(".", 1.0),
                     tok("2", 0.55, {"2": 0.55, "3": 0.30, "1": 0.10, "}": 0.05})] + chars("}")
    out = elicit.score_digit_expectation(json_payload(tokens, text))

    assert out["path"] == "decimal"
    assert out["score"] == pytest.approx(0.21 / 0.95)
    assert out["n_numeric_candidates"] == 3
    assert out["mass_on_numeric"] == pytest.approx(0.95)
    assert out["value_as_written"] == "0.2"


def test_whole_path_weights_full_values(elicit):
    """`0.85` arrives as one token, so the alternatives are whole values.

    Hand-computed: 0.85*0.6 + 0.9*0.3 + 0.8*0.1 = 0.51 + 0.27 + 0.08 = 0.86
    """
    text = '{"needs_human": 0.85}'
    tokens = chars('{"needs_human": ') + [
        tok("0.85", 0.6, {"0.85": 0.6, "0.9": 0.3, "0.8": 0.1})] + chars("}")
    out = elicit.score_digit_expectation(json_payload(tokens, text))

    assert out["path"] == "whole"
    assert out["score"] == pytest.approx(0.86)
    assert out["value_as_written"] == "0.85"


def test_integer_path_reads_zero_and_one(elicit):
    """No decimal point: the alternatives are 0 and 1. 0*0.8 + 1*0.2 = 0.2"""
    text = '{"needs_human": 0}'
    tokens = chars('{"needs_human": ') + [tok("0", 0.8, {"0": 0.8, "1": 0.2})] + chars("}")
    out = elicit.score_digit_expectation(json_payload(tokens, text))

    assert out["path"] == "integer"
    assert out["score"] == pytest.approx(0.2)


def test_trailing_punctuation_does_not_break_a_digit(elicit):
    """`2}` still reads as 2 — only the leading digits are taken."""
    text = '{"needs_human": 0.2}'
    tokens = chars('{"needs_human": ') + [tok("0", 1.0), tok(".", 1.0),
                                          tok("2}", 0.9, {"2}": 0.9, "3}": 0.1})]
    out = elicit.score_digit_expectation(json_payload(tokens, text))
    assert out["score"] == pytest.approx(0.2 * 0.9 + 0.3 * 0.1)


def test_out_of_range_alternatives_are_dropped(elicit):
    """A probability cannot be 5.0. Such a candidate is excluded, not clamped."""
    text = '{"needs_human": 0.4}'
    tokens = chars('{"needs_human": ') + [
        tok("0.4", 0.7, {"0.4": 0.7, "5.0": 0.2, "0.5": 0.1})] + chars("}")
    out = elicit.score_digit_expectation(json_payload(tokens, text))
    # Only 0.4 and 0.5 survive: (0.4*0.7 + 0.5*0.1) / 0.8
    assert out["score"] == pytest.approx((0.4 * 0.7 + 0.5 * 0.1) / 0.8)
    assert out["n_numeric_candidates"] == 2


def test_duplicate_surface_forms_are_summed_not_overwritten(elicit):
    """Two entries for the same token add up.

    A dict-assignment implementation would keep only the last and silently lose
    probability mass, which would show up as a wrong score rather than an error.
    """
    read = elicit.TokenRead(
        token="2", logprob=math.log(0.5),
        top=(("2", math.log(0.3)), ("2", math.log(0.2)), ("3", math.log(0.5))),
    )
    probs = read.probabilities()
    assert probs["2"] == pytest.approx(0.5)
    assert probs["3"] == pytest.approx(0.5)


def test_no_numeric_alternative_raises(elicit):
    text = '{"needs_human": 0.2}'
    tokens = chars('{"needs_human": ') + [tok("0", 1.0), tok(".", 1.0),
                                          tok("x", 1.0, {"x": 1.0})]
    with pytest.raises(ValueError, match="no numeric alternative"):
        elicit.score_digit_expectation(json_payload(tokens, text))


def test_payload_without_tokens_raises(elicit):
    with pytest.raises(ValueError, match="no token logprobs"):
        elicit.score_digit_expectation(json_payload([], '{"needs_human": 0.2}'))


# --------------------------------------------------------------------------- #
# Elicitor B
# --------------------------------------------------------------------------- #

def test_yes_no_normalises_over_the_pair(elicit):
    """P(Yes) / (P(Yes) + P(No)) = 0.62 / 0.98"""
    tokens = [tok("Yes", 0.62, {"Yes": 0.62, "No": 0.36, " ": 0.02})]
    out = elicit.score_yes_no(json_payload(tokens, "Yes"))
    assert out["score"] == pytest.approx(0.62 / 0.98)
    assert out["mass_on_yes_no"] == pytest.approx(0.98)


def test_yes_no_is_case_insensitive(elicit):
    tokens = [tok("yes", 0.7, {"yes": 0.7, "NO": 0.3})]
    out = elicit.score_yes_no(json_payload(tokens, "yes"))
    assert out["score"] == pytest.approx(0.7)


def test_yes_no_ignores_leading_whitespace_token(elicit):
    """The first *content* token is scored, not a leading space."""
    tokens = [tok(" ", 1.0), tok("No", 0.8, {"No": 0.8, "Yes": 0.2})]
    out = elicit.score_yes_no(json_payload(tokens, " No"))
    assert out["score"] == pytest.approx(0.2)


def test_yes_no_without_either_answer_raises(elicit):
    tokens = [tok("Maybe", 1.0, {"Maybe": 1.0})]
    with pytest.raises(ValueError):
        elicit.score_yes_no(json_payload(tokens, "Maybe"))


# --------------------------------------------------------------------------- #
# Scores are always recomputed, never read from the cache
# --------------------------------------------------------------------------- #

def test_score_payload_dispatches_to_both_scorers(elicit):
    a = elicit.score_payload(
        elicit.ELICITOR_A,
        json_payload(chars('{"needs_human": ') + [tok("0.3", 1.0)], '{"needs_human": 0.3}'))
    b = elicit.score_payload(elicit.ELICITOR_B,
                             json_payload([tok("Yes", 0.9, {"Yes": 0.9, "No": 0.1})], "Yes"))
    assert a["score"] == pytest.approx(0.3)
    assert b["score"] == pytest.approx(0.9)


def test_cache_entry_stores_the_payload_not_the_score(elicit):
    """An extraction fix must be re-runnable offline, which needs the payload."""
    payload = json_payload([tok("Yes", 0.9, {"Yes": 0.9, "No": 0.1})], "Yes")
    entry = elicit.cache_entry(
        elicitor=elicit.ELICITOR_B, case_id="c1", model="m",
        observation_hash="h", prompt_hash="p", payload=payload,
        generated_at="2026-01-01T00:00:00+00:00")
    assert entry["payload"] == payload
    assert "score" not in entry
    assert "score" not in json.dumps(entry)


# --------------------------------------------------------------------------- #
# Cache: schema, atomicity, byte-stability
# --------------------------------------------------------------------------- #

def test_load_missing_cache_returns_empty(elicit, tmp_path):
    cache = elicit.load_cache(tmp_path / "absent.json")
    assert cache == elicit.empty_cache()


def test_mismatched_schema_version_is_refused(elicit, tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"schema_version": 99, "entries": {}}))
    with pytest.raises(elicit.ElicitationError, match="schema_version"):
        elicit.load_cache(path)


def test_save_then_load_round_trips(elicit, tmp_path):
    path = tmp_path / "c.json"
    cache = elicit.empty_cache()
    cache["entries"]["k"] = {"case_id": "c1", "payload": {"text": "Yes"}}
    elicit.save_cache(path, cache)
    assert elicit.load_cache(path) == cache


def test_save_is_byte_identical_across_writes(elicit, tmp_path):
    """Determinism is what lets the reproduction check be a diff."""
    cache = elicit.empty_cache()
    for key in ("b", "a", "c"):
        cache["entries"][key] = {"case_id": key, "payload": {"text": key}}

    first, second = tmp_path / "1.json", tmp_path / "2.json"
    elicit.save_cache(first, cache)
    # Rebuild in a different insertion order; sort_keys must erase the difference.
    reordered = elicit.empty_cache()
    for key in ("c", "a", "b"):
        reordered["entries"][key] = {"case_id": key, "payload": {"text": key}}
    elicit.save_cache(second, reordered)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_text().endswith("\n")


def test_save_leaves_no_temp_file(elicit, tmp_path):
    path = tmp_path / "c.json"
    elicit.save_cache(path, elicit.empty_cache())
    assert [p.name for p in tmp_path.iterdir()] == ["c.json"]


def test_cache_key_is_elicitor_scoped(elicit):
    """Both elicitors score the same case, so case_id alone would collide."""
    a = elicit.cache_key(elicit.ELICITOR_A, "c1")
    b = elicit.cache_key(elicit.ELICITOR_B, "c1")
    assert a != b
    assert "c1" in a


# --------------------------------------------------------------------------- #
# Environment reading, and agreement with config.py
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("raw,expected", [
    ("true", True), ("True", True), ("1", True), ("yes", True), ("on", True),
    ("false", False), ("0", False), ("no", False), ("off", False),
])
def test_bool_parser_agrees_with_config(elicit, config, monkeypatch, raw, expected):
    """One vocabulary for booleans across the project.

    elicit.py cannot import config.py's private parser, so it mirrors it. Mirrored
    code drifts, and this is the test that notices. Both read the variable
    themselves, so the value goes in the environment and the *name* is the
    argument.
    """
    monkeypatch.setenv("LOGPROB_CACHE_ONLY", raw)
    assert elicit.read_bool_env("LOGPROB_CACHE_ONLY", not expected) is expected
    assert config._read_bool("LOGPROB_CACHE_ONLY", not expected) is expected


def test_bool_vocabularies_are_identical(elicit, config):
    """The mirrored token sets, compared directly.

    The parametrised test above only covers the spellings someone thought to list.
    This one fails the moment either side gains or loses a spelling.
    """
    assert elicit._TRUE_TOKENS == config._TRUE_TOKENS
    assert elicit._FALSE_TOKENS == config._FALSE_TOKENS


def test_bool_parser_raises_on_nonsense(elicit, config, monkeypatch):
    """Nonsense is refused, not silently defaulted.

    A typo'd LOGPROB_CACHE_ONLY=ture would otherwise fall back to False and make
    live calls during what the operator believed was a cache-only reproduction.
    """
    monkeypatch.setenv("LOGPROB_CACHE_ONLY", "banana")
    for default in (True, False):
        with pytest.raises(config.ConfigError, match="not a boolean"):
            elicit.read_bool_env("LOGPROB_CACHE_ONLY", default)
        with pytest.raises(config.ConfigError, match="not a boolean"):
            config._read_bool("LOGPROB_CACHE_ONLY", default)


def test_blank_value_is_treated_as_unset(elicit, monkeypatch):
    """`export LOGPROB_CACHE_ONLY=` is absence, not falsehood."""
    monkeypatch.setenv("LOGPROB_CACHE_ONLY", "   ")
    assert elicit.read_bool_env("LOGPROB_CACHE_ONLY", True) is True


def test_cache_only_defaults_off(elicit):
    assert elicit.cache_only() is False


def test_cache_only_reads_its_variable(elicit, monkeypatch):
    monkeypatch.setenv("LOGPROB_CACHE_ONLY", "true")
    assert elicit.cache_only() is True


def test_cache_path_is_absolute_and_overridable(elicit, monkeypatch, tmp_path):
    assert elicit.logprob_cache_path().is_absolute()
    monkeypatch.setenv("LOGPROB_CACHE_PATH", str(tmp_path / "x.json"))
    assert elicit.logprob_cache_path() == tmp_path / "x.json"


def test_observation_hash_matches_v1s(elicit, belief):
    """A logprob entry and a v1 belief entry for one case must agree.

    Same function, so a joined comparison across the two caches is sound and a
    changed message shows up as a changed hash in both.
    """
    ctx = elicit.CaseContext(turn_index=2, repeat_count=1)
    assert elicit.observation_hash("hello", ctx) == belief.input_hash("hello", ctx)


def test_observation_hash_changes_with_context(elicit):
    a = elicit.observation_hash("hello", elicit.CaseContext(turn_index=0, repeat_count=0))
    b = elicit.observation_hash("hello", elicit.CaseContext(turn_index=4, repeat_count=0))
    assert a != b


# --------------------------------------------------------------------------- #
# The network boundary
# --------------------------------------------------------------------------- #

def test_call_requests_logprobs_and_temperature_zero(elicit, fake_openai, monkeypatch):
    """The call has to ask for the alternatives, or there is nothing to score."""
    rec = fake_openai(raw_text='{"hot": 0.1, "warm": 0.3, "cold": 0.6, '
                               '"needs_human": 0.2}')
    try:
        elicit.call_with_logprobs(
            elicitor=elicit.ELICITOR_A, message="hi", context=None,
            model="gpt-4o-mini", api_key="sk-test")
    except Exception:
        # The stub SDK returns no logprobs, so payload extraction may fail. What
        # this test asserts is the request, which the recorder captured first.
        pass
    sent = rec.kwargs[-1]
    assert sent["logprobs"] is True
    assert sent["top_logprobs"] == elicit.TOP_LOGPROBS
    assert sent["temperature"] == 0
    assert sent["response_format"] == {"type": "json_object"}


def test_call_omits_json_mode_for_elicitor_b(elicit, fake_openai):
    rec = fake_openai(raw_text="Yes")
    try:
        elicit.call_with_logprobs(
            elicitor=elicit.ELICITOR_B, message="hi", context=None,
            model="gpt-4o-mini", api_key="sk-test")
    except Exception:
        pass
    sent = rec.kwargs[-1]
    assert "response_format" not in sent
    assert sent["max_tokens"] == elicit.max_tokens_for(elicit.ELICITOR_B)


def test_missing_sdk_is_a_clear_error(elicit, no_sdks):
    with pytest.raises(elicit.ElicitationError, match="openai"):
        elicit.call_with_logprobs(
            elicitor=elicit.ELICITOR_A, message="hi", context=None,
            model="m", api_key="sk-test")


def test_top_logprobs_is_within_the_api_limit(elicit):
    """The API caps top_logprobs at 20; asking for more is a hard error."""
    assert elicit.TOP_LOGPROBS <= 20
