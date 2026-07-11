"""Tests for LocalLlmClient — OpenAI SDK mocked (no real llama-server hit)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.llm_client import LlmResponse, create_llm_client
from core.llm_local import LocalLlmClient


def _fake_completion(text: str = "OK", finish: str = "stop", pt: int = 12, ct: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=pt, completion_tokens=ct),
    )


def _client_with(create_return: SimpleNamespace) -> LocalLlmClient:
    fake_sdk = MagicMock()
    fake_sdk.chat.completions.create.return_value = create_return
    return LocalLlmClient(url="http://local/v1", model="qwen", client=fake_sdk)


def test_generate_returns_valid_llm_response() -> None:
    client = _client_with(_fake_completion(text="OK", pt=12, ct=1))
    result = client.generate(system="be terse", messages=[{"role": "user", "content": "Reply with exactly: OK"}])

    assert isinstance(result, LlmResponse)
    assert result.content == "OK"
    assert result.stop_reason == "stop"
    assert result.usage == {"input_tokens": 12, "output_tokens": 1}
    assert result.cost_usd == 0.0


def test_generate_prepends_system_message() -> None:
    fake_sdk = MagicMock()
    fake_sdk.chat.completions.create.return_value = _fake_completion()
    client = LocalLlmClient(url="http://local/v1", model="qwen", client=fake_sdk)

    client.generate(system="SYS", messages=[{"role": "user", "content": "hi"}])

    _, kwargs = fake_sdk.chat.completions.create.call_args
    assert kwargs["messages"][0] == {"role": "system", "content": "SYS"}
    assert kwargs["messages"][1] == {"role": "user", "content": "hi"}
    assert kwargs["model"] == "qwen"


def test_factory_returns_local_when_backend_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_LLM_URL", "http://local/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen")
    client = create_llm_client("local")  # constructs OpenAI() but makes no network call
    assert isinstance(client, LocalLlmClient)


def test_missing_url_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCAL_LLM_URL", raising=False)
    with pytest.raises(ValueError, match="LOCAL_LLM_URL"):
        LocalLlmClient()
