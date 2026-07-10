"""Tests for RetrievalPolicy.build_context — 4-key bundle from a seeded session (keyless)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.memory.mem0_adapter import MemoryRecord
from core.memory.retrieval_policy import ContextBundle, RetrievalPolicy
from core.memory.world_state import Base, Character, StoryBeat, WorldState

SESSION = "sess-1"


class _FakeMemory:
    """Stands in for Mem0Adapter.search()."""

    def __init__(self, records: list[MemoryRecord]) -> None:
        self._records = records

    def search(self, query: str, top_k: int = 5) -> list[MemoryRecord]:
        return self._records[:top_k]


@pytest.fixture
def world(tmp_path: Path) -> Iterator[WorldState]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session:
        yield WorldState(session)


def _seed(world: WorldState) -> None:
    world.add(Character(session_id=SESSION, name="Aria", traits=["leal"], first_appeared_turn=1, last_seen_turn=9))
    world.add(Character(session_id=SESSION, name="Vex", traits=[], first_appeared_turn=2, last_seen_turn=8))
    world.add(StoryBeat(session_id=SESSION, summary="Aria descobre a traição", turn=8, importance=9, tags=[]))
    world.commit()


def test_build_context_returns_populated_bundle(world: WorldState) -> None:
    _seed(world)
    memory = _FakeMemory([
        MemoryRecord(id="m1", text="Turn 1\nPlayer: Aria chega ao castelo.", metadata={"turn": 1}),
        MemoryRecord(id="m2", text="Turn 2\nPlayer: Vex recebe uma carta.", metadata={"turn": 2}),
    ])
    policy = RetrievalPolicy(memory, world)

    bundle = policy.build_context(SESSION, current_turn=10, user_input="Onde está Aria?")

    assert isinstance(bundle, ContextBundle)
    assert len(bundle.raw_memories) > 0
    assert len(bundle.active_characters) > 0
    assert "Aria" in bundle.active_characters
    assert bundle.structured_facts == ["Aria descobre a traição"]
    assert bundle.token_estimate > 0


def test_active_characters_respect_recent_turns_window(world: WorldState) -> None:
    world.add(Character(session_id=SESSION, name="Recente", first_appeared_turn=1, last_seen_turn=20))
    world.add(Character(session_id=SESSION, name="Antigo", first_appeared_turn=1, last_seen_turn=2))
    world.commit()
    policy = RetrievalPolicy(_FakeMemory([]), world, recent_turns=10)

    bundle = policy.build_context(SESSION, current_turn=20, user_input="x")

    # window = turns >= 10; "Antigo" (last seen 2) is excluded
    assert bundle.active_characters == ["Recente"]


def test_top_memories_capped_by_top_k(world: WorldState) -> None:
    records = [MemoryRecord(id=f"m{i}", text=f"mem {i}", metadata={"turn": i}) for i in range(10)]
    policy = RetrievalPolicy(_FakeMemory(records), world, top_memories=3)

    bundle = policy.build_context(SESSION, current_turn=1, user_input="q")
    assert len(bundle.raw_memories) == 3
