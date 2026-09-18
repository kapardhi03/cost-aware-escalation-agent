"""Providers: the registry, each implementation, and JSON extraction."""

from __future__ import annotations

import json

import pytest


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

def test_expected_providers_are_registered(providers):
    assert set(providers.available_providers()) == {"openai", "google", "rule", "typesafe"}


def test_llm_chain_order_is_openai_then_google_then_typesafe(providers):
    assert [p.name for p in providers.llm_chain()] == ["openai", "google", "typesafe"]


def test_rule_is_not_in_the_llm_chain(providers):
    """Falling back to keywords is a policy decision in belief.py, not something
    the chain does on its own."""
    assert providers.RULE_PROVIDER not in [p.name for p in providers.llm_chain()]


def test_is_llm_flags(providers):
    assert providers.get_provider("openai").is_llm is True
    assert providers.get_provider("google").is_llm is True
    assert providers.get_provider("typesafe").is_llm is True
    assert providers.get_provider("rule").is_llm is False


def test_unknown_provider_lists_the_known_ones(providers):
    with pytest.raises(KeyError, match="registered"):
        providers.get_provider("anthropic")


def test_duplicate_registration_is_refused(providers):
    with pytest.raises(ValueError, match="already registered"):
        providers.register(providers.RuleProvider())


def test_nameless_provider_is_refused(providers):
    class Anonymous(providers.RuleProvider):
        name = ""
    with pytest.raises(ValueError, match="no name"):
        providers.register(Anonymous())


def test_a_new_provider_needs_no_change_to_belief(providers, belief, make_settings):
    """The point of the package: a provider is a drop-in."""
    class Constant(providers.Provider):
        name = "constant-test"
        is_llm = True

        def model_name(self, settings): return "constant-v1"
        def is_available(self, settings): return True
        def generate_raw(self, message, settings, context=None):
            return {"hot": 1.0, "warm": 0.0, "cold": 0.0, "needs_human": 0.5}

    providers.register(Constant())
    try:
        s = make_settings(provider="constant-test")
        b, meta = belief.get_belief("c", "hi", settings=s)
        assert b.readiness["hot"] == 1.0
        assert meta.provider == "constant-test" and meta.model == "constant-v1"
        assert meta.is_llm is True
    finally:
        providers._REGISTRY.pop("constant-test", None)


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #

def test_llm_availability_tracks_the_key(providers, make_settings):
    s = make_settings()
    assert providers.get_provider("openai").is_available(s) is False
    assert providers.get_provider("openai").is_available(
        s.with_overrides(openai_api_key="sk-x")) is True


def test_rule_provider_is_always_available(providers, make_settings):
    assert providers.get_provider("rule").is_available(make_settings()) is True


# --------------------------------------------------------------------------- #
# OpenAI provider
# --------------------------------------------------------------------------- #

def test_openai_receives_key_model_and_message(providers, make_settings, fake_openai):
    rec = fake_openai({"hot": .7, "warm": .2, "cold": .1, "needs_human": .3})
    s = make_settings(openai_api_key="sk-secret", openai_model="gpt-test")
    raw = providers.get_provider("openai").generate_raw("what is the price?", s)
    assert raw["hot"] == .7
    assert rec.keys == ["sk-secret"]          # key comes from Settings, not ambient env
    assert rec.models == ["gpt-test"]
    assert "what is the price?" in rec.messages[0]


def test_openai_error_propagates(providers, make_settings, fake_openai):
    fake_openai(error=RuntimeError("429 rate limited"))
    s = make_settings(openai_api_key="sk-x")
    with pytest.raises(RuntimeError, match="429"):
        providers.get_provider("openai").generate_raw("hi", s)


def test_openai_without_key_raises_before_calling(providers, make_settings, fake_openai):
    rec = fake_openai({"hot": 1, "warm": 0, "cold": 0, "needs_human": 0})
    with pytest.raises(Exception, match="OPENAI_API_KEY"):
        providers.get_provider("openai").generate_raw("hi", make_settings())
    assert rec.call_count == 0


def test_missing_sdk_gives_an_actionable_message(providers, make_settings, no_sdks):
    s = make_settings(openai_api_key="sk-x")
    with pytest.raises(providers.ProviderError, match="requirements.txt"):
        providers.get_provider("openai").generate_raw("hi", s)


# --------------------------------------------------------------------------- #
# Google provider
# --------------------------------------------------------------------------- #

def test_google_receives_key_model_and_message(providers, make_settings, fake_google):
    rec = fake_google({"hot": .1, "warm": .2, "cold": .7, "needs_human": .05})
    s = make_settings(google_api_key="g-secret", google_model="gemini-test")
    raw = providers.get_provider("google").generate_raw("just browsing", s)
    assert raw["cold"] == .7
    assert rec.keys == ["g-secret"] and rec.models == ["gemini-test"]
    assert "just browsing" in rec.messages[0]


def test_google_error_propagates(providers, make_settings, fake_google):
    fake_google(error=RuntimeError("503 unavailable"))
    with pytest.raises(RuntimeError, match="503"):
        providers.get_provider("google").generate_raw(
            "hi", make_settings(google_api_key="g-x"))


# --------------------------------------------------------------------------- #
# Rule provider — the offline floor
# --------------------------------------------------------------------------- #

def test_rule_scores_hot_language_highest(providers, make_settings):
    raw = providers.get_provider("rule").generate_raw(
        "what is the price, can I book a visit today?", make_settings())
    assert raw["hot"] == max(raw["hot"], raw["warm"], raw["cold"])


def test_rule_scores_cold_language_highest(providers, make_settings):
    raw = providers.get_provider("rule").generate_raw(
        "just browsing, no rush, maybe later", make_settings())
    assert raw["cold"] == max(raw["hot"], raw["warm"], raw["cold"])


def test_rule_raises_needs_human_on_escalation_language(providers, make_settings):
    p, s = providers.get_provider("rule"), make_settings()
    calm = p.generate_raw("what colours are available?", s)["needs_human"]
    hot = p.generate_raw("your contract terms are a scam, I want a refund and a lawyer",
                         s)["needs_human"]
    assert hot > calm


def test_needs_human_is_independent_of_readiness(providers, make_settings):
    """Locked design 0a: a hot lead can still need a human."""
    raw = providers.get_provider("rule").generate_raw(
        "I want to buy today but your contract terms look like a scam", make_settings())
    assert raw["hot"] > raw["cold"] and raw["needs_human"] > 0.3


@pytest.mark.parametrize("message", [
    "", "   ", "\n", "?", "a" * 10_000, "😀 price?", "PRICE AND BOOKING",
    "ok", ".", "12345",
])
def test_rule_always_returns_a_valid_distribution(providers, make_settings, message):
    raw = providers.get_provider("rule").generate_raw(message, make_settings())
    assert abs(raw["hot"] + raw["warm"] + raw["cold"] - 1.0) < 1e-9
    assert 0.0 <= raw["needs_human"] <= 1.0


def test_rule_handles_none_message(providers, make_settings):
    raw = providers.get_provider("rule").generate_raw(None, make_settings())
    assert abs(sum(raw[k] for k in ("hot", "warm", "cold")) - 1.0) < 1e-9


def test_rule_is_case_insensitive(providers, make_settings):
    p, s = providers.get_provider("rule"), make_settings()
    assert p.generate_raw("PRICE", s) == p.generate_raw("price", s)


def test_rule_needs_human_is_capped_at_one(providers, make_settings):
    flood = " ".join(["legal lawyer court complaint refund fraud manager contract",
                      "terms guarantee sue dispute angry scam misled cheated"])
    assert providers.get_provider("rule").generate_raw(
        flood, make_settings())["needs_human"] == 1.0


def test_rule_is_deterministic(providers, make_settings):
    p, s = providers.get_provider("rule"), make_settings()
    assert p.generate_raw("price today", s) == p.generate_raw("price today", s)


# --------------------------------------------------------------------------- #
# JSON extraction — real model output is not always clean
# --------------------------------------------------------------------------- #

PAYLOAD = {"hot": 0.5, "warm": 0.3, "cold": 0.2, "needs_human": 0.1}


@pytest.mark.parametrize("wrapper", [
    '{body}',
    '```json\n{body}\n```',
    '```\n{body}\n```',
    'Here is the JSON you asked for:\n{body}',
    '{body}\n\nLet me know if you need anything else.',
    '   \n {body} \n  ',
    'Sure!\n```json\n{body}\n```\nHope that helps.',
])
def test_extraction_survives_fences_and_prose(providers, wrapper):
    from providers.json_utils import extract_json
    assert extract_json(wrapper.format(body=json.dumps(PAYLOAD))) == PAYLOAD


def test_extraction_keeps_nested_objects(providers):
    from providers.json_utils import extract_json
    payload = {"hot": .5, "warm": .3, "cold": .2, "needs_human": .1,
               "why": {"signal": "asked for price"}}
    assert extract_json(json.dumps(payload))["why"]["signal"] == "asked for price"


@pytest.mark.parametrize("bad", ["", "no json here", "{unclosed", "}{",
                                 "{'single': 'quotes'}", "null", "[]"])
def test_unparseable_output_raises(providers, bad):
    from providers.json_utils import extract_json
    with pytest.raises(Exception):
        extract_json(bad)


def test_none_output_raises(providers):
    from providers.json_utils import extract_json
    with pytest.raises(ValueError, match="no text"):
        extract_json(None)


# --------------------------------------------------------------------------- #
# TypeSafe provider
# --------------------------------------------------------------------------- #

def test_typesafe_availability_tracks_key(providers, make_settings):
    p = providers.get_provider("typesafe")
    assert p.is_available(make_settings(typesafe_api_key="ts-x")) is True
    assert p.is_available(make_settings()) is False


def test_typesafe_receives_key_and_message(providers, make_settings, fake_typesafe):
    rec = fake_typesafe()
    p = providers.get_provider("typesafe")
    settings = make_settings(typesafe_api_key="apikey_test_123")
    result = p.generate_raw("I want to buy now", settings)
    assert result["hot"] == pytest.approx(0.2)
    assert result["warm"] == pytest.approx(0.5)
    assert result["cold"] == pytest.approx(0.3)
    assert result["needs_human"] == pytest.approx(0.4)
    assert rec.keys == ["Bearer apikey_test_123"]
    assert "I want to buy now" in rec.messages[0]


def test_typesafe_error_becomes_provider_error(providers, make_settings, fake_typesafe):
    import urllib.error
    fake_typesafe(error=urllib.error.URLError("network down"))
    p = providers.get_provider("typesafe")
    with pytest.raises(providers.ProviderError, match="connection failed"):
        p.generate_raw("Hi", make_settings(typesafe_api_key="ts-x"))


def test_typesafe_model_name(providers, make_settings):
    assert providers.get_provider("typesafe").model_name(make_settings()) == "jev"


def test_typesafe_is_last_in_chain(providers):
    chain = [p.name for p in providers.llm_chain()]
    assert chain[-1] == "typesafe"
