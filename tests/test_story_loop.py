"""Tests for StoryLoop v1 — narration + per-turn mem0 write, with LLM and memory mocked."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.story_loop import StoryLoop, TurnResult

SESSION = "story-sess"


def _llm(text: str = "A porta do castelo range ao anoitecer.", cost: float = 0.002) -> MagicMock:
    llm = MagicMock()
    llm.generate.return_value = SimpleNamespace(content=text, cost_usd=cost)
    return llm


def _memory(memory_id: str = "mem-1") -> MagicMock:
    mem = MagicMock()
    mem.add.return_value = memory_id
    return mem


def test_run_turn_returns_nonempty_narration_and_stores_memory() -> None:
    llm, mem = _llm(), _memory("mem-1")
    loop = StoryLoop(SESSION, memory=mem, llm=llm)

    result = loop.run_turn("Aria chega ao castelo.")

    assert isinstance(result, TurnResult)
    assert result.narrator_text.strip() != ""
    assert result.stored_memory_ids == ["mem-1"]
    assert result.cost_usd == 0.002
    mem.add.assert_called_once()


def test_run_turn_writes_one_memory_per_turn_with_turn_metadata() -> None:
    llm, mem = _llm(), _memory()
    loop = StoryLoop(SESSION, memory=mem, llm=llm)

    loop.run_turn("turno um")
    loop.run_turn("turno dois")

    assert mem.add.call_count == 2
    second_text, second_kwargs = mem.add.call_args_list[1]
    assert second_kwargs["metadata"] == {"turn": 2, "type": "story_turn"}
    # The stored record carries both the player input and the narration.
    assert "Player: turno dois" in second_text[0]
    assert "Narrator:" in second_text[0]


def test_run_turn_injects_user_input_into_system_prompt() -> None:
    llm, mem = _llm(), _memory()
    loop = StoryLoop(SESSION, memory=mem, llm=llm)

    loop.run_turn("Aria descobre a traição de Vex.")

    _, kwargs = llm.generate.call_args
    assert "Aria descobre a traição de Vex." in kwargs["system"]


def test_stored_memory_ids_empty_when_backend_returns_no_id() -> None:
    llm, mem = _llm(), _memory(memory_id="")
    loop = StoryLoop(SESSION, memory=mem, llm=llm)

    result = loop.run_turn("um turno")

    assert result.stored_memory_ids == []
