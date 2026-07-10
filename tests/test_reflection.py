"""Tests for FakeReflection — mechanical character extraction into world_state (keyless)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.memory.mem0_adapter import MemoryRecord
from core.memory.reflection import FakeReflection, Reflection, ReflectionResult
from core.memory.world_state import Base, Character, Location, Relation, StoryBeat, WorldState

SESSION = "sess-1"


class _FakeMemory:
    """Stands in for Mem0Adapter, returning canned turn records."""

    def __init__(self, records: list[MemoryRecord]) -> None:
        self._records = records

    def list_all(self) -> list[MemoryRecord]:
        return self._records


def _turn(turn: int, player_input: str) -> MemoryRecord:
    text = f"Turn {turn}\nPlayer: {player_input}\nNarrator: (fake narration)"
    return MemoryRecord(id=f"m{turn}", text=text, metadata={"turn": turn, "type": "story_turn"})


@pytest.fixture
def world(tmp_path: Path) -> Iterator[WorldState]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session:
        yield WorldState(session)


def _reflect(world: WorldState, records: list[MemoryRecord], since_turn: int = 0) -> ReflectionResult:
    return FakeReflection(world, _FakeMemory(records)).consolidate(SESSION, since_turn)


def test_fakereflection_satisfies_protocol(world: WorldState) -> None:
    assert isinstance(FakeReflection(world, _FakeMemory([])), Reflection)


def test_empty_turns_create_nothing(world: WorldState) -> None:
    result = _reflect(world, [])
    assert result == ReflectionResult(beats_created=0, characters_updated=0, relations_updated=0, cost_usd=0.0)
    assert world.list(Character, SESSION) == []


def test_single_character_extracted(world: WorldState) -> None:
    records = [
        _turn(1, "Aria entra no salão."),
        _turn(2, "Aria observa a corte."),
        _turn(3, "Aria saca a espada."),
    ]
    result = _reflect(world, records)

    names = [c.name for c in world.list(Character, SESSION)]
    assert "Aria" in names
    assert result.characters_updated >= 1
    assert result.beats_created == 1


def test_multiple_characters_extracted(world: WorldState) -> None:
    records = [
        _turn(1, "Aria e Vex discutem no salão."),
        _turn(2, "Aria acusa Vex de traição."),
        _turn(3, "Vex desafia Aria diante do rei."),
    ]
    _reflect(world, records)

    names = {c.name for c in world.list(Character, SESSION)}
    assert {"Aria", "Vex"} <= names


def test_repeated_event_does_not_duplicate(world: WorldState) -> None:
    records = [
        _turn(1, "Aria entra."),
        _turn(2, "Aria luta."),
        _turn(3, "Aria vence."),
    ]
    _reflect(world, records, since_turn=0)
    _reflect(world, records, since_turn=0)  # same turns again

    aria_rows = [c for c in world.list(Character, SESSION) if c.name == "Aria"]
    assert len(aria_rows) == 1  # updated, not duplicated


def test_location_extracted_from_place_phrase(world: WorldState) -> None:
    records = [
        _turn(1, "Aria chega ao castelo de Aldrath."),
        _turn(2, "Aria cruza o reino de Morwyn."),
        _turn(3, "Aria retorna ao castelo de Aldrath."),
    ]
    _reflect(world, records)

    names = {loc.name for loc in world.list(Location, SESSION)}
    assert {"Aldrath", "Morwyn"} <= names
    # deduped by name despite two "castelo de Aldrath" mentions
    assert len([loc for loc in world.list(Location, SESSION) if loc.name == "Aldrath"]) == 1


def test_relation_links_top_two_characters_without_duplicating(world: WorldState) -> None:
    records = [
        _turn(1, "Aria e Vex discutem."),
        _turn(2, "Aria acusa Vex."),
        _turn(3, "Vex desafia Aria."),
    ]
    result = _reflect(world, records, since_turn=0)
    assert result.relations_updated == 1
    rels = world.list(Relation, SESSION)
    assert len(rels) == 1
    assert rels[0].kind == "co-ocorrencia"

    # same top-2 pair again -> no duplicate relation
    again = _reflect(world, records, since_turn=0)
    assert again.relations_updated == 0
    assert len(world.list(Relation, SESSION)) == 1


def test_single_character_creates_no_relation(world: WorldState) -> None:
    result = _reflect(world, [_turn(1, "Aria."), _turn(2, "Aria."), _turn(3, "Aria.")])
    assert result.relations_updated == 0
    assert world.list(Relation, SESSION) == []


def test_counts_are_non_negative(world: WorldState) -> None:
    result = _reflect(world, [_turn(1, "Aria."), _turn(2, "Aria."), _turn(3, "Aria.")])
    assert result.beats_created >= 0
    assert result.characters_updated >= 0
    assert result.relations_updated >= 0
    assert result.cost_usd >= 0.0
    assert world.list(StoryBeat, SESSION)  # a beat was recorded
