"""LlmClient Protocol, LlmResponse model, and the backend factory.

The concrete impls live elsewhere: llm_anthropic.py (real, Sprint 3+) and
llm_fakes.py (deterministic stub). Sprints 1-2 run entirely on the fake — no API
key, no cost — so the whole wiring is validated before any real measurement.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

DEFAULT_BACKEND = "fake"


class LlmResponse(BaseModel):
    content: str
    stop_reason: str
    usage: dict[str, int]
    cost_usd: float


@runtime_checkable
class LlmClient(Protocol):
    """Narrative engine interface. Both backends implement this."""

    def generate(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> LlmResponse: ...


def create_llm_client(backend: str | None = None, **kwargs: Any) -> LlmClient:
    """Return the LlmClient impl selected by LLM_BACKEND (default 'fake')."""
    backend = (backend or os.environ.get("LLM_BACKEND", DEFAULT_BACKEND)).lower()
    if backend == "fake":
        from core.llm_fakes import FakeLlmClient

        return FakeLlmClient(**kwargs)
    if backend == "anthropic":
        from core.llm_anthropic import AnthropicLlmClient

        return AnthropicLlmClient(**kwargs)
    if backend == "local":
        from core.llm_local import LocalLlmClient

        return LocalLlmClient(**kwargs)
    raise ValueError(f"Unknown LLM_BACKEND {backend!r} (expected 'fake', 'anthropic', or 'local')")
