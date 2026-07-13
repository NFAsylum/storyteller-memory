"""AnthropicLlmClient — real LLM backend (Sprint 3+): bounded retry, timeout, cost logging."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

import anthropic
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from core.llm_client import LlmResponse

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_TOKENS = 1024

# Hardcoded USD price per 1M tokens as (input, output). Pinned to CLAUDE.md's model;
# extend when a new model is introduced.
_PRICE_PER_MTOK: MappingProxyType[str, tuple[float, float]] = MappingProxyType(
    {
        "claude-sonnet-4-6": (3.00, 15.00),
    }
)


class LlmError(Exception):
    """Base error for the Anthropic LLM client."""


class LlmTimeoutError(LlmError):
    """The Anthropic API call exceeded the configured timeout."""


def _is_retryable(exc: BaseException) -> bool:
    # Timeouts get a dedicated error instead of retrying — a call already past its
    # deadline is unlikely to succeed on a blind retry, and the caller needs to
    # distinguish "slow" from "rate limited".
    if isinstance(exc, anthropic.APITimeoutError):
        return False
    return isinstance(
        exc,
        (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError),
    )


class AnthropicLlmClient:
    """LlmClient impl over anthropic.Anthropic with our own retry/cost policy."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 30.0,
        client: Any | None = None,
    ) -> None:
        if model not in _PRICE_PER_MTOK:
            raise LlmError(f"No price table entry for model {model!r}")
        self.model = model
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        # Disable the SDK's own retry so tenacity is the single retry authority.
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=timeout_s, max_retries=0
        )

    def generate(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> LlmResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
            "temperature": 0,  # deterministic decoding (F1.5); accepted on claude-sonnet-4-6
        }
        if system is not None:
            kwargs["system"] = system
        if tools is not None:
            kwargs["tools"] = tools

        raw = self._call_with_retry(kwargs)
        response = self._to_response(raw)
        logger.info(
            "llm call model=%s in=%d out=%d cost=$%.6f",
            self.model,
            response.usage["input_tokens"],
            response.usage["output_tokens"],
            response.cost_usd,
        )
        return response

    def _call_with_retry(self, kwargs: dict[str, Any]) -> Any:
        retryer = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=1, min=self._retry_min_wait, max=self._retry_max_wait
            ),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        try:
            return retryer(lambda: self._client.messages.create(**kwargs))
        except anthropic.APITimeoutError as exc:
            raise LlmTimeoutError(f"Anthropic call timed out after {self.timeout_s}s") from exc

    def _to_response(self, raw: Any) -> LlmResponse:
        text = "".join(
            getattr(block, "text", "")
            for block in raw.content
            if getattr(block, "type", None) == "text"
        )
        usage = {
            "input_tokens": raw.usage.input_tokens,
            "output_tokens": raw.usage.output_tokens,
        }
        return LlmResponse(
            content=text,
            stop_reason=raw.stop_reason or "",
            usage=usage,
            cost_usd=self._cost(usage),
        )

    def _cost(self, usage: dict[str, int]) -> float:
        price_in, price_out = _PRICE_PER_MTOK[self.model]
        return (
            usage["input_tokens"] / 1_000_000 * price_in
            + usage["output_tokens"] / 1_000_000 * price_out
        )
