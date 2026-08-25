"""
Shared fixtures.

Two things every test here depends on.

1. Isolation from the developer's real environment. A `.env` on the machine
   running the suite must never change a result, and a stray OPENAI_API_KEY must
   never cause a test to make a paid call. `clean_env` strips every variable the
   project reads, and settings are always built with load_env_files=False.

2. Providers that don't touch the network. `fake_openai` / `fake_google` install
   stub SDK modules, so the real code path — including the SDK import inside the
   provider — runs exactly as it would in production, against a scripted reply.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import belief as belief_mod          # noqa: E402
import calibrate as calibrate_mod    # noqa: E402
import config as config_mod          # noqa: E402
import elicit as elicit_mod          # noqa: E402
import providers as providers_pkg    # noqa: E402

PROJECT_VARS = (
    "BELIEF_PROVIDER", "BELIEF_ALLOW_RULE_FALLBACK", "BELIEF_CACHE_PATH",
    "BELIEF_CACHE_ONLY",
    "LOGPROB_CACHE_PATH", "LOGPROB_CACHE_ONLY",
    "OPENAI_API_KEY", "OPENAI_MODEL", "GOOGLE_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_MODEL",
)


@pytest.fixture
def belief():
    return belief_mod


@pytest.fixture
def calibrate():
    return calibrate_mod


@pytest.fixture
def config():
    return config_mod


@pytest.fixture
def elicit():
    return elicit_mod


@pytest.fixture
def providers():
    return providers_pkg


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Every test starts from a known-empty configuration environment."""
    for var in PROJECT_VARS:
        monkeypatch.delenv(var, raising=False)
    config_mod.reset_cache()
    yield
    config_mod.reset_cache()


@pytest.fixture
def make_settings(tmp_path):
    """A valid Settings for tests, built directly rather than from the environment.

    Deliberately not routed through load_settings(): strict mode is the default
    now, so a keyless load raises, and most tests here want a working baseline
    rather than a re-test of configuration loading. Tests that care about how
    configuration is *read* call load_settings() themselves.

    The baseline is permissive (allow_rule_fallback=True) so that a test asking
    for the keyword provider does not have to restate it every time. Tests of the
    strict gate set it explicitly.
    """
    def _make(**overrides):
        config_mod.reset_cache()
        base = config_mod.Settings(
            provider="auto",
            allow_rule_fallback=True,
            openai_model=config_mod.DEFAULT_OPENAI_MODEL,
            google_model=config_mod.DEFAULT_GOOGLE_MODEL,
            cache_path=tmp_path / "cache.json",
            openai_api_key=None,
            google_api_key=None,
        )
        overrides.setdefault("cache_path", tmp_path / "cache.json")
        return config_mod._validate(dataclasses.replace(base, **overrides))
    return _make


class RecordingSDK:
    """Captures what a provider passed to its SDK."""

    def __init__(self):
        self.keys: list[str] = []
        self.models: list[str] = []
        self.messages: list[str] = []
        # Everything past model/messages. Needed to assert that a request asked
        # for logprobs at all — the belief path never sets them, the elicitation
        # path is meaningless without them.
        self.kwargs: list[dict] = []

    @property
    def call_count(self) -> int:
        return len(self.models)


@pytest.fixture
def fake_openai(monkeypatch):
    """Install a stub `openai` module. Returns the recorder."""
    def _install(payload=None, error=None, raw_text=None):
        rec = RecordingSDK()

        class _Completions:
            def create(self, model=None, messages=None, **kwargs):
                rec.models.append(model)
                rec.messages.append(messages[-1]["content"] if messages else "")
                rec.kwargs.append(kwargs)
                if error is not None:
                    raise error
                text = raw_text if raw_text is not None else json.dumps(payload)
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(
                        message=types.SimpleNamespace(content=text))])

        class _Client:
            def __init__(self, api_key=None, **kwargs):
                rec.keys.append(api_key)
                self.chat = types.SimpleNamespace(completions=_Completions())

        module = types.ModuleType("openai")
        module.OpenAI = _Client
        monkeypatch.setitem(sys.modules, "openai", module)
        return rec
    return _install


@pytest.fixture
def fake_google(monkeypatch):
    """Install a stub `google.genai` module. Returns the recorder."""
    def _install(payload=None, error=None, raw_text=None):
        rec = RecordingSDK()

        class _Models:
            def generate_content(self, model=None, contents=None, **kwargs):
                rec.models.append(model)
                rec.messages.append(contents or "")
                rec.kwargs.append(kwargs)
                if error is not None:
                    raise error
                text = raw_text if raw_text is not None else json.dumps(payload)
                return types.SimpleNamespace(text=text)

        class _Client:
            def __init__(self, api_key=None, **kwargs):
                rec.keys.append(api_key)
                self.models = _Models()

        google = types.ModuleType("google")
        genai = types.ModuleType("google.genai")
        gtypes = types.ModuleType("google.genai.types")
        genai.Client = _Client
        gtypes.GenerateContentConfig = lambda **kw: types.SimpleNamespace(**kw)
        genai.types = gtypes
        google.genai = genai
        for name, mod in (("google", google), ("google.genai", genai),
                          ("google.genai.types", gtypes)):
            monkeypatch.setitem(sys.modules, name, mod)
        return rec
    return _install


@pytest.fixture
def no_sdks(monkeypatch):
    """Make both SDK imports fail, as on a machine with nothing installed."""
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) \
        else __builtins__.__import__

    def _blocked(name, *args, **kwargs):
        if name in ("openai", "google", "google.genai") or name.startswith("google."):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _blocked)
