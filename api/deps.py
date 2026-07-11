"""Injectable backend resources for the API (overridable in tests via dependency_overrides)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session as DbSession

from core.db import get_engine, get_sessionmaker
from core.llm_client import LlmClient, create_llm_client
from core.memory.mem0_adapter import Mem0Adapter, build_mem0_memory
from core.memory.world_state import Base


@dataclass
class Backend:
    session_factory: Callable[[], DbSession]
    llm: LlmClient
    memory_for: Callable[[str], Any]  # session_id -> memory adapter


_backend: Backend | None = None


def build_backend() -> Backend:
    engine = get_engine()
    Base.metadata.create_all(engine)
    session_factory = get_sessionmaker(engine)
    llm = create_llm_client()
    # Build ONE mem0 Memory (heavy import) and share it across sessions via user_id.
    shared_memory = build_mem0_memory()

    def memory_for(session_id: str) -> Mem0Adapter:
        return Mem0Adapter(session_id, memory=shared_memory)

    return Backend(session_factory=session_factory, llm=llm, memory_for=memory_for)


def get_backend() -> Backend:
    global _backend
    if _backend is None:
        _backend = build_backend()
    return _backend
