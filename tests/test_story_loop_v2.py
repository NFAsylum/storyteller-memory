"""S2.4 integration: StoryLoop with retrieval + reflection wired (in-memory fakes, keyless)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.llm_fakes import FakeLlmClient
from core.memory.mem0_adapter import MemoryRecord
from core.memory.reflection import FakeReflection
from core.memory.retrieval_policy import RetrievalPolicy
from core.memory.world_state import Base, Character, StoryBeat, WorldState
from core.story_loop import StoryLoop

SESSION = "sess-1"
ARIA_TURNS = [
    "Aria chega ao castelo.",
    "Aria observa a corte.",
    "Aria luta no salão.",
    "Aria vence o duelo.",
    "Aria descansa à noite.",
    "Aria parte ao amanhecer.",
]


class _FakeMem0:
    """In-memory Mem0Adapter stand-in: add/search/list_all/clear."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []
        self._n = 0

    def add(self, text: str, metadata: dict | None = None) -> str:
        self._n += 1
        rid = f"m{self._n}"
        self._records.append(MemoryRecord(id=rid, text=text, metadata=metadata or {}))
        return rid

    def search(self, query: str, top_k: int = 5) -> list[MemoryRecord]:
        return self._records[-top_k:]

    def list_all(self) -> list[MemoryRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


class _CapturingLlm(FakeLlmClient):
    def __init__(self) -> None:
        super().__init__()
        self.prompts: list[str] = []

    def generate(self, system, messages, tools=None):
        self.prompts.append(system)
        return super().generate(system, messages, tools)


@pytest.fixture
def world(tmp_path: Path) -> Iterator[WorldState]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session:
        yield WorldState(session)


def _loop(world: WorldState, llm: _CapturingLlm) -> StoryLoop:
    memory = _FakeMem0()
    return StoryLoop(
        SESSION,
        memory=memory,
        llm=llm,
        retrieval_policy=RetrievalPolicy(memory, world),
        reflection=FakeReflection(world, memory),
        reflect_every=5,
    )


def test_bundle_reaches_the_prompt(world: WorldState) -> None:
    llm = _CapturingLlm()
    loop = _loop(world, llm)
    for text in ARIA_TURNS:  # 6 turns; reflection fires at turn 5 and extracts "Aria"
        loop.run_turn(text)

    # The turn-6 prompt carries the world_state character back into the context.
    assert "Active characters: Aria" in llm.prompts[5]


def test_retrieved_context_is_populated(world: WorldState) -> None:
    loop = _loop(world, _CapturingLlm())
    result = None
    for text in ARIA_TURNS:
        result = loop.run_turn(text)

    assert result is not None
    assert result.retrieved_context["active_characters"] == ["Aria"]
    assert len(result.retrieved_context["raw_memories"]) > 0
    assert result.retrieved_context["token_estimate"] > 0


def test_reflection_fires_every_five_turns(world: WorldState) -> None:
    loop = _loop(world, _CapturingLlm())
    for text in (ARIA_TURNS * 3)[:15]:  # 15 turns -> reflection at 5, 10, 15
        loop.run_turn(text)

    assert len(world.list(StoryBeat, SESSION)) == 3  # one beat per consolidation
    assert "Aria" in {c.name for c in world.list(Character, SESSION)}


def test_v1_behavior_without_policy_or_reflection(world: WorldState) -> None:
    memory = _FakeMem0()
    loop = StoryLoop(SESSION, memory=memory, llm=FakeLlmClient())  # no retrieval/reflection
    for text in ARIA_TURNS[:5]:
        result = loop.run_turn(text)

    assert result.retrieved_context["raw_memories"] == []
    assert world.list(StoryBeat, SESSION) == []  # reflection never ran
