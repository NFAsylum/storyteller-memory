"""Tests for FakeReflection — mechanical character extraction into world_state (keyless)."""

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.llm_client import LlmResponse
from core.memory.mem0_adapter import MemoryRecord
from core.memory.reflection import (
    FakeReflection,
    LlmReflection,
    Reflection,
    ReflectionResult,
)
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


# --- LlmReflection (LLM mocked) --------------------------------------------------

_VALID_EXTRACTION = {
    "new_characters": [
        {"name": "Aria", "traits": ["leal"], "first_appeared_turn": 1},
        {"name": "Vex", "traits": ["ambicioso"], "first_appeared_turn": 2},
    ],
    "character_updates": [],
    "new_locations": [{"name": "Aldrath", "description": "castelo", "first_visited_turn": 1}],
    "relations": [{"a": "Aria", "b": "Vex", "kind": "rivalidade", "valence": -2, "since_turn": 2}],
    "beats": [{"summary": "Aria descobre a traição de Vex", "importance": 8, "turn": 3, "tags": ["traição"]}],
}


def _llm_response(content: str, cost: float = 0.02) -> LlmResponse:
    return LlmResponse(content=content, stop_reason="stop", usage={"input_tokens": 100, "output_tokens": 50}, cost_usd=cost)


def _mock_llm(*contents: str, cost: float = 0.02) -> MagicMock:
    llm = MagicMock()
    llm.generate.side_effect = [_llm_response(c, cost) for c in contents]
    return llm


def _records() -> list[MemoryRecord]:
    return [
        _turn(1, "Aria chega ao castelo de Aldrath."),
        _turn(2, "Vex recebe uma carta secreta."),
        _turn(3, "Aria descobre a traição de Vex."),
    ]


def test_llm_reflection_persists_structured_facts(world: WorldState) -> None:
    llm = _mock_llm(json.dumps(_VALID_EXTRACTION))
    result = LlmReflection(llm, world, _FakeMemory(_records())).consolidate(SESSION, since_turn=0)

    assert {c.name for c in world.list(Character, SESSION)} == {"Aria", "Vex"}
    assert {loc.name for loc in world.list(Location, SESSION)} == {"Aldrath"}
    rels = world.list(Relation, SESSION)
    assert len(rels) == 1 and rels[0].kind == "rivalidade"
    assert world.list(StoryBeat, SESSION)[0].summary == "Aria descobre a traição de Vex"
    assert result.beats_created == 1
    assert result.relations_updated == 1
    assert result.cost_usd == pytest.approx(0.02)


def test_llm_reflection_retries_on_malformed_json(world: WorldState) -> None:
    # First reply is prose (no JSON), second is a valid object wrapped in fences.
    llm = _mock_llm("desculpe, aqui vai:", "```json\n" + json.dumps(_VALID_EXTRACTION) + "\n```")
    result = LlmReflection(llm, world, _FakeMemory(_records())).consolidate(SESSION, since_turn=0)

    assert llm.generate.call_count == 2
    assert {c.name for c in world.list(Character, SESSION)} == {"Aria", "Vex"}
    assert result.cost_usd == pytest.approx(0.04)  # two calls billed


def test_llm_reflection_gives_up_after_retries(world: WorldState) -> None:
    llm = _mock_llm("no json here", "still no json", "nope", cost=0.01)
    reflection = LlmReflection(llm, world, _FakeMemory(_records()), max_retries=2)
    result = reflection.consolidate(SESSION, since_turn=0)

    assert llm.generate.call_count == 3  # initial + 2 retries
    assert world.list(Character, SESSION) == []  # nothing persisted
    assert result.beats_created == 0
    assert result.characters_updated == 0
    assert result.relations_updated == 0
    assert result.cost_usd == pytest.approx(0.03)
