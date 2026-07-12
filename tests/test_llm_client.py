"""Tests for the LLM layer: AnthropicLlmClient (mocked), FakeLlmClient, and the factory."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from core.llm_anthropic import AnthropicLlmClient, LlmError, LlmTimeoutError
from core.llm_client import LlmClient, LlmResponse, create_llm_client
from core.llm_fakes import FakeLlmClient

# --- AnthropicLlmClient (all mocked — no network) --------------------------------


def _fake_message(
    text: str = "Hello there",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    stop_reason: str = "end_turn",
) -> SimpleNamespace:
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
    return anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def _anthropic_with(create_mock: MagicMock) -> AnthropicLlmClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = create_mock
    return AnthropicLlmClient(client=fake_sdk, retry_min_wait=0, retry_max_wait=0)


def test_anthropic_generate_returns_response_with_cost() -> None:
    create = MagicMock(return_value=_fake_message(input_tokens=1_000_000, output_tokens=1_000_000))
    result = _anthropic_with(create).generate(system="sys", messages=[{"role": "user", "content": "hi"}])

    assert isinstance(result, LlmResponse)
    assert result.content == "Hello there"
    assert result.stop_reason == "end_turn"
    assert result.usage["input_tokens"] == 1_000_000
    # 1M input * $3/MTok + 1M output * $15/MTok = $18.00
    assert result.cost_usd == pytest.approx(18.0)
    create.assert_called_once()


def test_anthropic_retries_after_rate_limit() -> None:
    create = MagicMock(side_effect=[_rate_limit_error(), _fake_message()])
    result = _anthropic_with(create).generate(system=None, messages=[{"role": "user", "content": "hi"}])

    assert result.content == "Hello there"
    assert create.call_count == 2


def test_anthropic_raises_specific_error_on_timeout() -> None:
    create = MagicMock(side_effect=_timeout_error())
    client = _anthropic_with(create)

    with pytest.raises(LlmTimeoutError):
        client.generate(system=None, messages=[{"role": "user", "content": "hi"}])
    create.assert_called_once()


def test_anthropic_unknown_model_is_rejected() -> None:
    with pytest.raises(LlmError):
        AnthropicLlmClient(model="not-a-real-model", client=MagicMock())


# --- FakeLlmClient ---------------------------------------------------------------


def test_fake_is_deterministic_and_nonempty() -> None:
    fake = FakeLlmClient()
    messages = [{"role": "user", "content": "Aria chega ao castelo."}]
    first = fake.generate(system="sys", messages=messages)
    second = fake.generate(system="sys", messages=messages)

    assert first.content == second.content  # same input -> same output
    assert first.content.strip() != ""
    assert "Aria chega ao castelo." in first.content  # echoes the user input


def test_fake_is_free_and_needs_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = FakeLlmClient().generate(system="s", messages=[{"role": "user", "content": "x"}])

    assert result.cost_usd == 0.0
    assert result.usage["input_tokens"] > 0
    assert isinstance(result, LlmResponse)


def test_fake_different_inputs_give_different_narrations() -> None:
    fake = FakeLlmClient()
    a = fake.generate(system="sys", messages=[{"role": "user", "content": "turno A"}])
    b = fake.generate(system="sys", messages=[{"role": "user", "content": "turno B"}])
    assert a.content != b.content


# --- Factory ---------------------------------------------------------------------


def test_factory_defaults_to_fake_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = create_llm_client()

    assert isinstance(client, FakeLlmClient)
    assert isinstance(client, LlmClient)  # satisfies the runtime-checkable Protocol


def test_factory_returns_anthropic_when_requested() -> None:
    client = create_llm_client("anthropic", api_key="sk-ant-test")
    assert isinstance(client, AnthropicLlmClient)


def test_factory_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError):
        create_llm_client("gpt")
