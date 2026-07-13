"""Tests for StoryLoop v1 — narration + per-turn mem0 write, using the real FakeLlmClient.

Only mem0 is mocked (its real backend needs heavy deps); the LLM is the deterministic
FakeLlmClient, which is more robust than a hand-rolled mock.
"""

from unittest.mock import MagicMock

from core.llm_fakes import FakeLlmClient
from core.story_loop import StoryLoop, TurnResult

SESSION = "story-sess"


def _memory(memory_id: str = "mem-1") -> MagicMock:
    mem = MagicMock()
    mem.add.return_value = memory_id
    return mem


def test_run_turn_returns_nonempty_narration_and_stores_memory() -> None:
    mem = _memory("mem-1")
    loop = StoryLoop(SESSION, memory=mem, llm=FakeLlmClient())

    result = loop.run_turn("Aria chega ao castelo.")

    assert isinstance(result, TurnResult)
    assert result.narrator_text.strip() != ""
    assert result.stored_memory_ids == ["mem-1"]
    assert result.cost_usd == 0.0  # fake is free
    mem.add.assert_called_once()


def test_run_turn_is_deterministic() -> None:
    loop_a = StoryLoop(SESSION, memory=_memory(), llm=FakeLlmClient())
    loop_b = StoryLoop(SESSION, memory=_memory(), llm=FakeLlmClient())

    assert loop_a.run_turn("mesmo input").narrator_text == loop_b.run_turn("mesmo input").narrator_text


def test_run_turn_writes_one_memory_per_turn_with_turn_metadata() -> None:
    mem = _memory()
    loop = StoryLoop(SESSION, memory=mem, llm=FakeLlmClient())

    loop.run_turn("turno um")
    loop.run_turn("turno dois")

    assert mem.add.call_count == 2
    second_text, second_kwargs = mem.add.call_args_list[1]
    assert second_kwargs["metadata"] == {"turn": 2, "type": "story_turn"}
    assert "Player: turno dois" in second_text[0]
    assert "Narrator:" in second_text[0]


def test_run_turn_injects_user_input_into_prompt() -> None:
    captured: dict[str, object] = {}

    class _CapturingLlm(FakeLlmClient):
        def generate(self, system, messages, tools=None, max_tokens=None):
            captured["system"] = system
            return super().generate(system, messages, tools)

    loop = StoryLoop(SESSION, memory=_memory(), llm=_CapturingLlm())
    loop.run_turn("Aria descobre a traição de Vex.")

    assert "Aria descobre a traição de Vex." in captured["system"]


def test_stored_memory_ids_empty_when_backend_returns_no_id() -> None:
    loop = StoryLoop(SESSION, memory=_memory(memory_id=""), llm=FakeLlmClient())
    assert loop.run_turn("um turno").stored_memory_ids == []


def test_run_turn_passes_max_tokens_from_config() -> None:
    from core.session_config import SessionConfig, max_tokens_for

    captured: dict[str, object] = {}

    class _Cap(FakeLlmClient):
        def generate(self, system, messages, tools=None, max_tokens=None):
            captured["max_tokens"] = max_tokens
            return super().generate(system, messages, tools)

    config = SessionConfig(target_length="long")
    StoryLoop(SESSION, memory=_memory(), llm=_Cap(), config=config).run_turn("um turno")
    assert captured["max_tokens"] == max_tokens_for(config)
    assert captured["max_tokens"] > max_tokens_for(SessionConfig(target_length="brief"))
