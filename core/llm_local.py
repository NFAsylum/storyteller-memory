"""LocalLlmClient — LLM backend via a local OpenAI-compatible server (llama-server).

No paid API and no rate limits, so Sprint 3 measurements can run on a local model
(Qwen2.5-Coder-7B) instead of Anthropic. cost_usd is always 0.0. The measurement stays
valid because the same model is used for both baseline and augmented configs.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

from openai import OpenAI

from core.llm_client import LlmResponse

DEFAULT_TIMEOUT_S = 120.0  # local model is slower than a hosted API
DEFAULT_MAX_TOKENS = 1024
DEFAULT_MODEL = "local-model"
DEFAULT_TEMPERATURE = 0.0  # deterministic decoding (F1.5)
DEFAULT_SEED = 42  # fixed seed so harness runs are reproducible; override via LOCAL_LLM_SEED
# llama-server ignores the key but the OpenAI SDK requires a non-empty field.
LOCAL_API_KEY = "local"

MODEL_QUERY_TIMEOUT_S = 2.0  # keep /health snappy even if llama-server is unreachable
_MODEL_CACHE_TTL_S = 30.0  # avoid hitting llama-server on every /health request
# Live-detected model id, cached with its wall-clock timestamp (0.0 = never queried).
_MODEL_CACHE: dict[str, Any] = {"value": None, "at": 0.0}


def _fetch_local_model(base_url: str, timeout_s: float) -> str | None:
    """GET {base_url}/models and return the first model id.

    Returns None when the server is unreachable or times out, or the sentinel
    "local-unknown-format" when it answers but not in the OpenAI /v1/models shape.
    """
    url = base_url.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310 - fixed local URL
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any network/parse failure means "unreachable"
        return None
    try:
        return str(payload["data"][0]["id"])
    except (KeyError, IndexError, TypeError):
        return "local-unknown-format"


def detect_local_model(
    url: str | None = None, timeout_s: float = MODEL_QUERY_TIMEOUT_S
) -> str | None:
    """Model id llama-server actually has loaded (cached 30s), or None if unreachable.

    Env config (LOCAL_LLM_MODEL) is only a hint: llama-server serves whatever model it
    has loaded regardless of the requested id, so a truthful status must query the server
    itself. The 30s cache keeps /health from hitting llama-server on every request.
    """
    now = time.time()
    if now - _MODEL_CACHE["at"] < _MODEL_CACHE_TTL_S:
        return _MODEL_CACHE["value"]
    base_url = url or os.environ.get("LOCAL_LLM_URL")
    value = _fetch_local_model(base_url, timeout_s) if base_url else None
    _MODEL_CACHE["value"] = value
    _MODEL_CACHE["at"] = now
    return value


class LocalLlmClient:
    """LlmClient impl over an OpenAI-compatible /v1 endpoint (no retry, cost is 0)."""

    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        seed: int | None = None,
        client: Any | None = None,
    ) -> None:
        url = url or os.environ.get("LOCAL_LLM_URL")
        if not url:
            raise ValueError("LOCAL_LLM_URL is not set (required for LLM_BACKEND=local)")
        self.url = url
        self.model = model or os.environ.get("LOCAL_LLM_MODEL") or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed if seed is not None else int(os.environ.get("LOCAL_LLM_SEED", DEFAULT_SEED))
        # Local server has no 429s, so no exponential retry — just a generous timeout.
        self._client = client or OpenAI(base_url=url, api_key=LOCAL_API_KEY, timeout=timeout_s)

    def generate(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> LlmResponse:
        # tools are accepted for Protocol parity but not forwarded — story narration
        # doesn't use them, and Anthropic->OpenAI schema translation is out of scope here.
        chat_messages: list[dict[str, Any]] = []
        if system is not None:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        # Anti-repetition sampling (T-REP.1): temperature=0 alone lets the 7B lock into
        # repeated phrasing (or an English drift); the penalties nudge it off already-emitted
        # tokens without breaking seed-determinism — they only bite when a repeat would win.
        # repeat_penalty is llama.cpp-specific (via extra_body); ignored by OpenAI cloud.
        completion = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            messages=chat_messages,
            temperature=self.temperature,
            seed=self.seed,
            frequency_penalty=0.3,
            presence_penalty=0.3,
            extra_body={"repeat_penalty": 1.15},
        )
        choice = completion.choices[0]
        usage = completion.usage
        return LlmResponse(
            content=choice.message.content or "",
            stop_reason=choice.finish_reason or "",
            usage={
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            },
            cost_usd=0.0,
        )
