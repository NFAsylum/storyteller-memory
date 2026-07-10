"""Facade over mem0 that isolates the dependency and scopes every memory to a session.

The concrete backend (decided for dev): Anthropic LLM + local HuggingFace embedder +
local FAISS store — no OpenAI, no external vector DB. mem0's session scoping is its
``user_id`` field, which we map 1:1 to our ``session_id``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

DEFAULT_LLM_MODEL = "claude-sonnet-4-6"
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBED_DIMS = 384  # all-MiniLM-L6-v2 output dimensionality
DEFAULT_STORAGE_PATH = "./.mem0_data"
COLLECTION_NAME = "storyteller"


@dataclass(frozen=True)
class MemoryRecord:
    """One stored memory as returned by the adapter (named to avoid clashing with mem0.Memory)."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None


def build_mem0_config(
    api_key: str | None,
    storage_path: str,
    llm_model: str,
    embed_model: str,
) -> dict[str, Any]:
    """mem0 config for the Anthropic-LLM + local-HF-embedder + local-FAISS backend."""
    return {
        "llm": {
            "provider": "anthropic",
            "config": {"model": llm_model, "api_key": api_key},
        },
        "embedder": {
            "provider": "huggingface",
            "config": {"model": embed_model},
        },
        "vector_store": {
            "provider": "faiss",
            "config": {
                "collection_name": COLLECTION_NAME,
                "path": os.path.join(storage_path, "faiss"),
                "embedding_model_dims": DEFAULT_EMBED_DIMS,
            },
        },
    }


class Mem0Adapter:
    """Thin, session-scoped wrapper over a mem0 Memory instance."""

    def __init__(
        self,
        session_id: str,
        memory: Any | None = None,
        *,
        api_key: str | None = None,
        storage_path: str | None = None,
        llm_model: str = DEFAULT_LLM_MODEL,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        self.session_id = session_id
        self._memory = memory or self._build_memory(api_key, storage_path, llm_model, embed_model)

    @staticmethod
    def _build_memory(
        api_key: str | None,
        storage_path: str | None,
        llm_model: str,
        embed_model: str,
    ) -> Any:
        # Lazy import: mem0's heavy backend deps (sentence-transformers, faiss) are only
        # needed for a real instance, not for unit tests that inject a fake memory.
        from mem0 import Memory as Mem0Memory

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        resolved_path = storage_path or os.environ.get("MEM0_STORAGE_PATH", DEFAULT_STORAGE_PATH)
        config = build_mem0_config(resolved_key, resolved_path, llm_model, embed_model)
        return Mem0Memory.from_config(config)

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        # infer=False stores the turn verbatim (one entry per call) instead of running
        # the LLM to derive facts — that derivation is Sprint 2's reflection step, and
        # verbatim storage is what makes the per-turn list_all() check deterministic.
        raw = self._memory.add(
            text,
            user_id=self.session_id,
            metadata=metadata or {},
            infer=False,
        )
        records = self._to_records(raw)
        return records[0].id if records else ""

    def search(self, query: str, top_k: int = 5) -> list[MemoryRecord]:
        return self._to_records(self._memory.search(query, user_id=self.session_id, limit=top_k))

    def list_all(self) -> list[MemoryRecord]:
        return self._to_records(self._memory.get_all(user_id=self.session_id))

    def clear(self) -> None:
        self._memory.delete_all(user_id=self.session_id)

    @staticmethod
    def _to_records(raw: Any) -> list[MemoryRecord]:
        # mem0 returns either {"results": [...]} (current) or a bare list (older shapes).
        items = raw.get("results", []) if isinstance(raw, dict) else (raw or [])
        return [
            MemoryRecord(
                id=str(item.get("id", "")),
                text=item.get("memory", item.get("text", "")),
                metadata=item.get("metadata") or {},
                score=item.get("score"),
            )
            for item in items
        ]
