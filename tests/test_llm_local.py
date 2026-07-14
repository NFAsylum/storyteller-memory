"""Tests for LocalLlmClient — OpenAI SDK mocked (no real llama-server hit)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core import llm_local
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
    # F1.5: deterministic decoding
    assert kwargs["temperature"] == 0.0
    assert kwargs["seed"] == 42


def test_generate_passes_anti_repetition_sampling() -> None:
    fake_sdk = MagicMock()
    fake_sdk.chat.completions.create.return_value = _fake_completion()
    client = LocalLlmClient(url="http://local/v1", model="qwen", client=fake_sdk)

    client.generate(system="s", messages=[{"role": "user", "content": "hi"}])

    _, kwargs = fake_sdk.chat.completions.create.call_args
    assert kwargs["frequency_penalty"] == 0.3
    assert kwargs["presence_penalty"] == 0.3
    assert kwargs["extra_body"] == {"repeat_penalty": 1.15}


def test_factory_returns_local_when_backend_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_LLM_URL", "http://local/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen")
    client = create_llm_client("local")  # constructs OpenAI() but makes no network call
    assert isinstance(client, LocalLlmClient)


def test_missing_url_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCAL_LLM_URL", raising=False)
    with pytest.raises(ValueError, match="LOCAL_LLM_URL"):
        LocalLlmClient()


# --- T-STATUS.1: live model detection (env is a hint, llama-server is the truth) ---


class _FakeResp:
    """Minimal stand-in for the urllib.request.urlopen context manager."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _reset_model_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_local, "_MODEL_CACHE", {"value": None, "at": 0.0})


def test_detect_local_model_returns_first_id_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_model_cache(monkeypatch)
    calls: list[str] = []

    def fake_fetch(base_url: str, timeout_s: float) -> str:
        calls.append(base_url)
        return "qwen2.5-coder-7b"

    monkeypatch.setattr(llm_local, "_fetch_local_model", fake_fetch)
    monkeypatch.setenv("LOCAL_LLM_URL", "http://local/v1")

    assert llm_local.detect_local_model() == "qwen2.5-coder-7b"
    assert llm_local.detect_local_model() == "qwen2.5-coder-7b"  # served from the 30s cache
    assert len(calls) == 1  # llama-server hit at most once within the TTL


def test_detect_local_model_unreachable_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_model_cache(monkeypatch)
    monkeypatch.setattr(llm_local, "_fetch_local_model", lambda base, timeout: None)
    monkeypatch.setenv("LOCAL_LLM_URL", "http://local/v1")
    assert llm_local.detect_local_model() is None


def test_detect_local_model_no_url_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_model_cache(monkeypatch)
    monkeypatch.delenv("LOCAL_LLM_URL", raising=False)
    assert llm_local.detect_local_model() is None


def test_fetch_local_model_parses_openai_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"data": [{"id": "qwen2.5-coder-7b"}]}).encode("utf-8")
    monkeypatch.setattr(llm_local.urllib.request, "urlopen", lambda url, timeout: _FakeResp(body))
    assert llm_local._fetch_local_model("http://local/v1", 2.0) == "qwen2.5-coder-7b"


def test_fetch_local_model_unknown_shape_returns_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_local.urllib.request, "urlopen", lambda url, timeout: _FakeResp(b'{"weird": true}')
    )
    assert llm_local._fetch_local_model("http://local/v1", 2.0) == "local-unknown-format"
