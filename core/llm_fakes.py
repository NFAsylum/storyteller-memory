"""FakeLlmClient — deterministic templated narration for Sprints 1-2 (no API, no cost).

Determinism is the whole point: the same (system, messages) always yields the same
narration, so the wiring and the eval harness can be validated without touching the
real API. The seed is a hash of the prompt, so there's no randomness or clock use.
"""

from __future__ import annotations

import hashlib
from typing import Any

from core.llm_client import LlmResponse

_TEMPLATES: tuple[str, ...] = (
    "As tochas tremeluzem no salão. {echo} O ar pesa com o que ainda não foi dito.",
    "A cena se desenrola em silêncio. {echo} Ao longe, um sino soa uma única vez.",
    "Passos ecoam pela pedra fria. {echo} Uma sombra hesita à beira da luz.",
    "O vento cruza as ameias. {echo} Algo mudou, e todos sentem, sem saber nomear.",
    "A corte prende a respiração. {echo} O momento se estende, tenso como um arco retesado.",
)


class FakeLlmClient:
    """Deterministic LlmClient stub: hash-seeded template, cost_usd=0, no API key."""

    def __init__(self, templates: tuple[str, ...] | None = None) -> None:
        self._templates = templates or _TEMPLATES

    def generate(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LlmResponse:
        user_text = str(messages[-1]["content"]) if messages else ""
        seed = self._seed(system, user_text)
        template = self._templates[seed % len(self._templates)]
        content = template.format(echo=f"O que se desenrola: {user_text}")
        usage = {
            "input_tokens": self._approx_tokens(system) + self._approx_tokens(user_text),
            "output_tokens": self._approx_tokens(content),
        }
        return LlmResponse(content=content, stop_reason="end_turn", usage=usage, cost_usd=0.0)

    @staticmethod
    def _seed(system: str, user_text: str) -> int:
        digest = hashlib.sha256(f"{system}\x00{user_text}".encode()).hexdigest()
        return int(digest, 16)

    @staticmethod
    def _approx_tokens(text: str) -> int:
        # 4 chars ≈ 1 token, matching the project-wide estimate.
        return max(1, len(text) // 4)
