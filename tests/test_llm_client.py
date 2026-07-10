"""Tests for core.llm_client — success, 429 retry, and timeout paths (all mocked)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from core.llm_client import LlmClient, LlmError, LlmResponse, LlmTimeoutError


def _fake_message(
    text: str = "Hello there",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    stop_reason: str = "end_turn",
) -> SimpleNamespace:
    """Minimal stand-in for anthropic.types.Message (only the fields we read)."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model="claude-sonnet-4-6",
    )


def _rate_limit_error() -> anthropic.RateLimitError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, request=request)
    return anthropic.RateLimitError("rate limited", response=response, body=None)


def _timeout_error() -> anthropic.APITimeoutError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APITimeoutError(request=request)


def _client_with(create_mock: MagicMock) -> LlmClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = create_mock
    # Zero waits keep the retry test fast.
    return LlmClient(client=fake_sdk, retry_min_wait=0, retry_max_wait=0)


def test_generate_returns_response_with_cost() -> None:
    create = MagicMock(return_value=_fake_message(input_tokens=1_000_000, output_tokens=1_000_000))
    client = _client_with(create)

    result = client.generate(system="You narrate.", messages=[{"role": "user", "content": "hi"}])

    assert isinstance(result, LlmResponse)
    assert result.content == "Hello there"
    assert result.stop_reason == "end_turn"
    assert result.usage.input_tokens == 1_000_000
    # 1M input * $3/MTok + 1M output * $15/MTok = $18.00
    assert result.cost_usd == pytest.approx(18.0)
    create.assert_called_once()


def test_generate_retries_after_rate_limit() -> None:
    create = MagicMock(side_effect=[_rate_limit_error(), _fake_message()])
    client = _client_with(create)

    result = client.generate(system=None, messages=[{"role": "user", "content": "hi"}])

    assert result.content == "Hello there"
    assert create.call_count == 2


def test_generate_raises_specific_error_on_timeout() -> None:
    create = MagicMock(side_effect=_timeout_error())
    client = _client_with(create)

    with pytest.raises(LlmTimeoutError):
        client.generate(system=None, messages=[{"role": "user", "content": "hi"}])

    # Timeout is not retried — it fails fast with the dedicated error.
    create.assert_called_once()


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(LlmError):
        LlmClient(model="not-a-real-model", client=MagicMock())
