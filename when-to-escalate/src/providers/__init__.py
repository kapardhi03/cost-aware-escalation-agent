"""
providers — the registry of belief sources.

Adding a provider is: write a Provider subclass in this package, then register it
below. Nothing in belief.py changes.

`LLM_CHAIN_ORDER` is the order the automatic chain tries real models in. The rule
provider is deliberately not in it — falling back to keywords is a policy
decision made in belief.py against `allow_rule_fallback`, not something the chain
does on its own.
"""

from __future__ import annotations

from .base import Provider, ProviderError
from .google_provider import GoogleProvider
from .openai_provider import OpenAIProvider
from .rule_provider import RuleProvider
from .typesafe_provider import TypeSafeProvider

_REGISTRY: dict[str, Provider] = {}


def register(provider: Provider) -> Provider:
    """Add a provider to the registry. Duplicate names are a programming error."""
    if not provider.name:
        raise ValueError(f"{type(provider).__name__} has no name")
    if provider.name in _REGISTRY:
        raise ValueError(f"provider {provider.name!r} is already registered")
    _REGISTRY[provider.name] = provider
    return provider


register(OpenAIProvider())
register(GoogleProvider())
register(RuleProvider())
register(TypeSafeProvider())

#: Real-model providers, in the order the automatic chain tries them.
LLM_CHAIN_ORDER = ("openai", "google", "typesafe")

#: The rule provider's registry name, kept as a constant so nothing hardcodes it.
RULE_PROVIDER = "rule"


def get_provider(name: str) -> Provider:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"unknown provider {name!r}; registered: {', '.join(sorted(_REGISTRY))}"
        ) from None


def available_providers() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def llm_chain() -> tuple[Provider, ...]:
    return tuple(get_provider(n) for n in LLM_CHAIN_ORDER)


__all__ = [
    "Provider", "ProviderError", "OpenAIProvider", "GoogleProvider",
    "RuleProvider", "TypeSafeProvider", "register", "get_provider",
    "available_providers", "llm_chain", "LLM_CHAIN_ORDER", "RULE_PROVIDER",
]
