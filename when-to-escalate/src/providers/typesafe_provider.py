"""
providers/typesafe_provider.py — TypeSafe System One (Jev) belief source.

Jev returns typed probabilities, not generated text. Two primitives map
directly to the project's belief shape:

- Choice → readiness distribution over {hot, warm, cold}
- Noul   → independent P(needs_human)

Both questions go in one API call. Uses urllib.request (stdlib) — no new
dependency, matching the project's stdlib-only convention (see elicit.py).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from .base import Provider, ProviderError
from .prompt import render_observation

if TYPE_CHECKING:
    from ..config import Settings

_API_URL = "https://api.typesafe.ai/v1/systemone"
_TIMEOUT = 30  # seconds


class TypeSafeProvider(Provider):
    name = "typesafe"
    is_llm = True

    def model_name(self, settings: "Settings") -> str:
        return "jev"

    def is_available(self, settings: "Settings") -> bool:
        return settings.has_key("typesafe")

    def generate_raw(self, message: str, settings: "Settings", context=None) -> dict:
        api_key = settings.require_key("typesafe")
        observation = render_observation(message, context)

        body = json.dumps({
            "state": observation,
            "model": "jev-latest",
            "questions": {
                "readiness": {
                    "type": "choice",
                    "instructions": (
                        "How ready is this inbound lead to buy? Classify "
                        "based on urgency, specificity, and commitment signals."
                    ),
                    "criteria": {
                        "hot": (
                            "Buyer is ready to act within days — explicit "
                            "urgency, specific product mentions, schedule language"
                        ),
                        "warm": (
                            "Genuine interest but no commitment signal — "
                            "exploring, comparing, asking general questions"
                        ),
                        "cold": (
                            "No buying intent — spam, support query, "
                            "unsubscribe, wrong channel, or pure information"
                        ),
                    },
                },
                "needs_human": {
                    "type": "noul",
                    "instructions": (
                        "Does this message require a human touch? Consider: "
                        "legal question, emotional distress, VIP hint, explicit "
                        "'talk to a person' request, or anything an automated "
                        "reply would fumble."
                    ),
                },
            },
        }).encode()

        req = urllib.request.Request(
            _API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise ProviderError(
                self.name, f"HTTP {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ProviderError(
                self.name, f"connection failed: {exc.reason}"
            ) from exc
        except (json.JSONDecodeError, OSError) as exc:
            raise ProviderError(self.name, str(exc)) from exc

        try:
            answers = data["answers"]
            readiness_probs = answers["readiness"]["probabilities"]
            needs_human_val = answers["needs_human"]["noul"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(
                self.name, f"unexpected response shape: {exc}"
            ) from exc

        return {
            "hot": float(readiness_probs["hot"]),
            "warm": float(readiness_probs["warm"]),
            "cold": float(readiness_probs["cold"]),
            "needs_human": float(needs_human_val),
        }
