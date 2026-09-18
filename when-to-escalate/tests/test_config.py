"""Configuration: parsing, validation, path resolution, and secret handling."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #

def test_defaults_are_strict(config, monkeypatch):
    """Build decision 21: a run that says nothing gets LLM-only, not a mixture."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    s = config.load_settings(reload=True, load_env_files=False)
    assert s.provider == "auto"
    assert s.allow_rule_fallback is False
    assert s.openai_model == config.DEFAULT_OPENAI_MODEL
    assert s.google_model == config.DEFAULT_GOOGLE_MODEL


def test_an_unconfigured_keyless_run_is_refused(config):
    """The safety property the default exists for. Silence must not yield keywords.

    Before the default flipped, this configuration ran happily and filled the
    cache with keyword beliefs indistinguishable from LLM ones.
    """
    with pytest.raises(config.ConfigError, match="neither OPENAI_API_KEY"):
        config.load_settings(reload=True, load_env_files=False)


def test_keyword_scoring_must_be_opted_into(config, monkeypatch):
    """Two ways in, both explicit: pin the provider, or allow the fallback."""
    monkeypatch.setenv("BELIEF_PROVIDER", "rule")
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    assert config.load_settings(reload=True, load_env_files=False).provider == "rule"

    monkeypatch.delenv("BELIEF_PROVIDER")
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    s = config.load_settings(reload=True, load_env_files=False)
    assert s.allow_rule_fallback is True and s.live_providers == ()


def test_repo_root_contains_this_project(config):
    assert (config.find_repo_root() / "when-to-escalate").is_dir()


def test_repo_root_falls_back_without_git(config, tmp_path):
    """An exported copy with no .git must still resolve, not raise."""
    assert config.find_repo_root(start=tmp_path).exists()


# --------------------------------------------------------------------------- #
# Boolean parsing — every accepted token, and the rejection of everything else
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("token", ["1", "true", "TRUE", "True", "t", "yes", "Y", "on", " on "])
def test_truthy_tokens(config, monkeypatch, token):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", token)
    assert config.load_settings(reload=True, load_env_files=False).allow_rule_fallback is True


@pytest.mark.parametrize("token", ["0", "false", "FALSE", "f", "no", "N", "off", " off "])
def test_falsy_tokens(config, monkeypatch, token):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", token)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")   # strict mode needs a usable provider
    assert config.load_settings(reload=True, load_env_files=False).allow_rule_fallback is False


@pytest.mark.parametrize("token", ["maybe", "2", "", "  ", "yess", "null", "None"])
def test_non_boolean_is_rejected_or_defaulted(config, monkeypatch, token):
    """Blank falls back to the default; a non-blank non-boolean is an error that
    names the variable, so a typo in .env is traceable to its line."""
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", token)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")   # so only the token is under test
    if not token.strip():
        assert config.load_settings(reload=True, load_env_files=False).allow_rule_fallback is False
    else:
        with pytest.raises(config.ConfigError, match="BELIEF_ALLOW_RULE_FALLBACK"):
            config.load_settings(reload=True, load_env_files=False)


# --------------------------------------------------------------------------- #
# Provider validation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", ["auto", "openai", "google", "typesafe", "rule"])
def test_valid_providers_accepted(config, monkeypatch, name):
    monkeypatch.setenv("BELIEF_PROVIDER", name)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("GOOGLE_API_KEY", "g-x")
    monkeypatch.setenv("TYPE_SAFE_AI_API", "ts-x")
    if name == "rule":
        # Pinning the keyword provider under a strict default is a contradiction,
        # and is reported as one rather than silently resolved either way.
        monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    assert config.load_settings(reload=True, load_env_files=False).provider == name


def test_provider_is_case_insensitive(config, monkeypatch):
    monkeypatch.setenv("BELIEF_PROVIDER", "OpenAI")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    assert config.load_settings(reload=True, load_env_files=False).provider == "openai"


@pytest.mark.parametrize("name", ["anthropic", "gpt4", "llama", "rules", "openai2"])
def test_unknown_provider_is_rejected(config, monkeypatch, name):
    monkeypatch.setenv("BELIEF_PROVIDER", name)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    with pytest.raises(config.ConfigError, match="not recognised"):
        config.load_settings(reload=True, load_env_files=False)


@pytest.mark.parametrize("name", ["  openai  ", "OPENAI ", "\tgoogle\n"])
def test_provider_name_whitespace_is_tolerated(config, monkeypatch, name):
    """A trailing space in .env is a typo that should not break a run."""
    monkeypatch.setenv("BELIEF_PROVIDER", name)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("GOOGLE_API_KEY", "g-x")
    assert config.load_settings(reload=True, load_env_files=False).provider == name.strip().lower()


def test_pinned_llm_provider_without_key_fails_at_load(config, monkeypatch):
    """Fail before the run starts, not on the first case."""
    monkeypatch.setenv("BELIEF_PROVIDER", "openai")
    with pytest.raises(config.ConfigError, match="OPENAI_API_KEY"):
        config.load_settings(reload=True, load_env_files=False)


# --------------------------------------------------------------------------- #
# The contradictions that matter — a strict run that cannot possibly succeed
# --------------------------------------------------------------------------- #

def test_strict_mode_with_no_keys_is_rejected(config, monkeypatch):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "false")
    with pytest.raises(config.ConfigError, match="neither OPENAI_API_KEY nor GOOGLE_API_KEY"):
        config.load_settings(reload=True, load_env_files=False)


def test_rule_provider_contradicts_strict_mode(config, monkeypatch):
    monkeypatch.setenv("BELIEF_PROVIDER", "rule")
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "false")
    with pytest.raises(config.ConfigError, match="contradicts"):
        config.load_settings(reload=True, load_env_files=False)


@pytest.mark.parametrize("key_var", ["OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"])
def test_strict_mode_passes_with_any_one_key(config, monkeypatch, key_var):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "false")
    monkeypatch.setenv(key_var, "some-key")
    s = config.load_settings(reload=True, load_env_files=False)
    assert s.allow_rule_fallback is False and len(s.live_providers) == 1


# --------------------------------------------------------------------------- #
# Keys
# --------------------------------------------------------------------------- #

def test_gemini_alias_and_precedence(config, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "from-google")
    assert config.load_settings(reload=True, load_env_files=False).google_api_key == "from-gemini"


def test_google_key_used_when_gemini_absent(config, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "from-google")
    assert config.load_settings(reload=True, load_env_files=False).google_api_key == "from-google"


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_key_counts_as_unset(config, monkeypatch, blank):
    """A commented-out or emptied .env line must not look like a usable key.

    Under strict-by-default this is also a safety property: a blanked key must
    stop the run, not quietly demote it to keyword scoring."""
    monkeypatch.setenv("OPENAI_API_KEY", blank)
    with pytest.raises(config.ConfigError):
        config.load_settings(reload=True, load_env_files=False)


def test_key_whitespace_is_stripped(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "  sk-padded  ")
    assert config.load_settings(reload=True, load_env_files=False).openai_api_key == "sk-padded"


def test_live_providers_order_and_membership(config, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    assert config.load_settings(reload=True, load_env_files=False).live_providers == ("google",)
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    assert config.load_settings(reload=True, load_env_files=False).live_providers == ("openai", "google")


def test_require_key_names_the_missing_variable(config, monkeypatch):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    s = config.load_settings(reload=True, load_env_files=False)
    with pytest.raises(config.ConfigError, match="OPENAI_API_KEY"):
        s.require_key("openai")


# --------------------------------------------------------------------------- #
# Secrets must never be printable. This repo is public.
# --------------------------------------------------------------------------- #

SECRET = "sk-proj-SUPERSECRETVALUE-9999"


def test_repr_does_not_leak_the_key(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    text = repr(config.load_settings(reload=True, load_env_files=False))
    assert SECRET not in text
    assert "<set:" in text and "9999" in text     # length + last 4 for identification


def test_describe_does_not_leak_the_key(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    text = config.load_settings(reload=True, load_env_files=False).describe()
    assert SECRET not in text and "key set" in text


def test_describe_marks_missing_keys_and_blocked_fallback(config, monkeypatch):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    text = config.load_settings(reload=True, load_env_files=False).describe()
    assert "NO KEY" in text and "BLOCKED" in text


# --------------------------------------------------------------------------- #
# Path resolution — the bug that would silently split the cache in two
# --------------------------------------------------------------------------- #

REL = "when-to-escalate/data/belief_cache.json"


def test_relative_path_is_independent_of_cwd(config, monkeypatch, tmp_path):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    monkeypatch.setenv("BELIEF_CACHE_PATH", REL)
    origin = Path.cwd()
    try:
        os.chdir(config.find_repo_root())
        from_root = config.load_settings(reload=True, load_env_files=False).cache_path
        os.chdir(tmp_path)
        from_elsewhere = config.load_settings(reload=True, load_env_files=False).cache_path
    finally:
        os.chdir(origin)
    assert from_root == from_elsewhere, "same config must not yield two caches"


def test_resolved_path_is_absolute(config, monkeypatch):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    monkeypatch.setenv("BELIEF_CACHE_PATH", REL)
    assert config.load_settings(reload=True, load_env_files=False).cache_path.is_absolute()


def test_absolute_path_is_preserved(config, monkeypatch, tmp_path):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    target = tmp_path / "somewhere" / "c.json"
    monkeypatch.setenv("BELIEF_CACHE_PATH", str(target))
    assert config.load_settings(reload=True, load_env_files=False).cache_path == target.resolve()


def test_tilde_is_expanded(config, monkeypatch):
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    monkeypatch.setenv("BELIEF_CACHE_PATH", "~/beliefs.json")
    got = config.load_settings(reload=True, load_env_files=False).cache_path
    assert "~" not in str(got) and got.is_absolute()


# --------------------------------------------------------------------------- #
# Memoisation — a run must not see configuration change halfway through
# --------------------------------------------------------------------------- #

def test_settings_are_memoised(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    first = config.load_settings(reload=True, load_env_files=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-changed")
    assert config.load_settings(load_env_files=False) is first


def test_reload_picks_up_changes(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    config.load_settings(reload=True, load_env_files=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-changed")
    assert config.load_settings(reload=True, load_env_files=False).openai_model == "gpt-changed"


def test_reset_cache_forces_a_rebuild(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    first = config.load_settings(reload=True, load_env_files=False)
    config.reset_cache()
    assert config.load_settings(load_env_files=False) is not first


# --------------------------------------------------------------------------- #
# Overrides
# --------------------------------------------------------------------------- #

def test_settings_are_frozen(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    s = config.load_settings(reload=True, load_env_files=False)
    with pytest.raises(Exception):
        s.provider = "openai"


def test_with_overrides_does_not_mutate_the_original(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    s = config.load_settings(reload=True, load_env_files=False)
    other = s.with_overrides(openai_model="gpt-other")
    assert s.openai_model != "gpt-other" and other.openai_model == "gpt-other"


def test_with_overrides_still_validates(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    s = config.load_settings(reload=True, load_env_files=False)
    with pytest.raises(config.ConfigError):
        s.with_overrides(provider="rule", allow_rule_fallback=False)


def test_with_overrides_does_not_touch_environment(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    s = config.load_settings(reload=True, load_env_files=False)
    s.with_overrides(openai_model="gpt-other")
    assert "OPENAI_MODEL" not in os.environ


# --------------------------------------------------------------------------- #
# .env loading
# --------------------------------------------------------------------------- #

def test_env_file_is_read(config, monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("OPENAI_MODEL=gpt-from-file\nOPENAI_API_KEY=sk-from-file\n")
    monkeypatch.setattr(config, "_env_candidates", lambda: [env])
    s = config.load_settings(reload=True)
    assert s.openai_model == "gpt-from-file" and env in s.env_files


def test_real_environment_beats_the_env_file(config, monkeypatch, tmp_path):
    """CI secrets and an explicit export must not be clobbered by a stale file."""
    env = tmp_path / ".env"
    env.write_text("OPENAI_MODEL=gpt-from-file\nOPENAI_API_KEY=sk-from-file\n")
    monkeypatch.setattr(config, "_env_candidates", lambda: [env])
    monkeypatch.setenv("OPENAI_MODEL", "gpt-from-shell")
    assert config.load_settings(reload=True).openai_model == "gpt-from-shell"


def test_missing_env_file_is_not_fatal(config, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setattr(config, "_env_candidates", lambda: [tmp_path / "absent"])
    assert config.load_settings(reload=True).env_files == ()


# --------------------------------------------------------------------------- #
# Cache-only mode — reproducing the reported run without a key
# --------------------------------------------------------------------------- #
#
# The bug this closes: the committed cache covers every case, so re-running the
# experiment needs no network call, but validation demanded a live provider before
# the cache was ever consulted. A fresh clone could not reproduce the paper's
# numbers without a key it would never actually use.

def test_cache_only_lifts_the_keyless_strict_block(config, monkeypatch):
    monkeypatch.setenv("BELIEF_CACHE_ONLY", "true")
    s = config.load_settings(reload=True, load_env_files=False)
    assert s.cache_only is True
    assert s.allow_rule_fallback is False, "cache-only must not relax strictness"
    assert s.live_providers == ()


def test_keyless_strict_still_fails_without_cache_only(config):
    """The guard must not have been weakened for everyone."""
    with pytest.raises(config.ConfigError):
        config.load_settings(reload=True, load_env_files=False)


def test_cache_only_error_message_names_the_escape_hatch(config):
    with pytest.raises(config.ConfigError, match="BELIEF_CACHE_ONLY"):
        config.load_settings(reload=True, load_env_files=False)


def test_cache_only_contradicts_the_rule_fallback(config, monkeypatch):
    monkeypatch.setenv("BELIEF_CACHE_ONLY", "true")
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    with pytest.raises(config.ConfigError, match="contradicts"):
        config.load_settings(reload=True, load_env_files=False)


def test_cache_only_does_not_require_a_named_providers_key(config, monkeypatch):
    """provider=openai normally demands OPENAI_API_KEY. Cache-only generates
    nothing, so the key is genuinely unnecessary."""
    monkeypatch.setenv("BELIEF_PROVIDER", "openai")
    monkeypatch.setenv("BELIEF_CACHE_ONLY", "true")
    s = config.load_settings(reload=True, load_env_files=False)
    assert s.provider == "openai" and s.cache_only is True

    monkeypatch.delenv("BELIEF_CACHE_ONLY")
    with pytest.raises(config.ConfigError):
        config.load_settings(reload=True, load_env_files=False)


def test_cache_only_defaults_off(config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    assert config.load_settings(
        reload=True, load_env_files=False).cache_only is False


def test_cache_only_is_shown_in_describe(config, monkeypatch):
    monkeypatch.setenv("BELIEF_CACHE_ONLY", "true")
    text = config.load_settings(reload=True, load_env_files=False).describe()
    assert "cache only" in text and "no LLM call" in text


# --------------------------------------------------------------------------- #
# TypeSafe key handling
# --------------------------------------------------------------------------- #

def test_typesafe_key_read_from_env(config, monkeypatch):
    monkeypatch.setenv("TYPE_SAFE_AI_API", "apikey_from_env")
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    s = config.load_settings(reload=True, load_env_files=False)
    assert s.typesafe_api_key == "apikey_from_env"


def test_typesafe_key_in_live_providers(config, monkeypatch):
    monkeypatch.setenv("TYPE_SAFE_AI_API", "ts-k")
    monkeypatch.setenv("BELIEF_ALLOW_RULE_FALLBACK", "true")
    s = config.load_settings(reload=True, load_env_files=False)
    assert "typesafe" in s.live_providers


def test_typesafe_pinned_without_key_rejected(config, monkeypatch):
    monkeypatch.setenv("BELIEF_PROVIDER", "typesafe")
    with pytest.raises(config.ConfigError, match="TYPE_SAFE_AI_API"):
        config.load_settings(reload=True, load_env_files=False)


def test_typesafe_key_not_leaked_in_repr(config, monkeypatch):
    monkeypatch.setenv("TYPE_SAFE_AI_API", "apikey_secret_value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    text = repr(config.load_settings(reload=True, load_env_files=False))
    assert "apikey_secret_value" not in text
    assert "<set:" in text


def test_typesafe_key_not_leaked_in_describe(config, monkeypatch):
    monkeypatch.setenv("TYPE_SAFE_AI_API", "apikey_secret_value")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    text = config.load_settings(reload=True, load_env_files=False).describe()
    assert "apikey_secret_value" not in text
    assert "key set" in text
