"""Tests for Mem0Adapter — session scoping and result normalization, with mem0 mocked."""

from unittest.mock import MagicMock

from core.memory.mem0_adapter import Mem0Adapter, MemoryRecord, build_mem0_config

SESSION = "sess-42"


def _adapter(mem: MagicMock) -> Mem0Adapter:
    return Mem0Adapter(SESSION, memory=mem)


def test_add_scopes_to_session_and_returns_id() -> None:
    mem = MagicMock()
    mem.add.return_value = {"results": [{"id": "m1", "memory": "txt", "event": "ADD"}]}
    adapter = _adapter(mem)

    memory_id = adapter.add("Turn 1 ...", metadata={"turn": 1})

    assert memory_id == "m1"
    _, kwargs = mem.add.call_args
    assert kwargs["user_id"] == SESSION
    assert kwargs["infer"] is False
    assert kwargs["metadata"] == {"turn": 1}


def test_list_all_normalizes_results_dict() -> None:
    mem = MagicMock()
    mem.get_all.return_value = {
        "results": [
            {"id": "a", "memory": "first", "metadata": {"turn": 1}},
            {"id": "b", "memory": "second", "metadata": {"turn": 2}},
        ]
    }
    records = _adapter(mem).list_all()

    assert [r.id for r in records] == ["a", "b"]
    assert records[0] == MemoryRecord(id="a", text="first", metadata={"turn": 1})
    mem.get_all.assert_called_once_with(user_id=SESSION)


def test_records_handle_bare_list_shape() -> None:
    mem = MagicMock()
    mem.get_all.return_value = [{"id": "x", "memory": "solo"}]
    records = _adapter(mem).list_all()

    assert records == [MemoryRecord(id="x", text="solo", metadata={}, score=None)]


def test_search_passes_top_k_as_limit() -> None:
    mem = MagicMock()
    mem.search.return_value = {"results": [{"id": "s1", "memory": "hit", "score": 0.9}]}
    records = _adapter(mem).search("who is Aria?", top_k=3)

    assert records[0].score == 0.9
    mem.search.assert_called_once_with("who is Aria?", user_id=SESSION, limit=3)


def test_clear_delegates_to_delete_all() -> None:
    mem = MagicMock()
    _adapter(mem).clear()
    mem.delete_all.assert_called_once_with(user_id=SESSION)


def test_config_uses_anthropic_llm_local_embedder_and_faiss() -> None:
    config = build_mem0_config("sk-key", "/tmp/store", "claude-sonnet-4-6", "hf/model")
    assert config["llm"]["provider"] == "anthropic"
    assert config["llm"]["config"]["model"] == "claude-sonnet-4-6"
    assert config["embedder"]["provider"] == "huggingface"
    assert config["vector_store"]["provider"] == "faiss"
    assert config["vector_store"]["config"]["path"] == "/tmp/store/faiss"
