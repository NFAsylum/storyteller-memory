"""CRUD tests for the four world_state entities (SQLite, keyless)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.memory.world_state import (
    Base,
    Character,
    Location,
    Relation,
    StoryBeat,
    WorldState,
)

SESSION = "sess-1"


@pytest.fixture
def world(tmp_path: Path) -> Iterator[WorldState]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session:
        yield WorldState(session)


def test_character_crud_roundtrip(world: WorldState) -> None:
    aria = world.add(
        Character(session_id=SESSION, name="Aria", traits=["leal"], first_appeared_turn=1, last_seen_turn=1)
    )
    world.commit()

    # Read + JSON list round-trips portably
    fetched = world.get(Character, aria.id)
    assert fetched is not None
    assert fetched.name == "Aria"
    assert fetched.traits == ["leal"]

    # Update
    fetched.traits = ["leal", "corajosa"]
    fetched.last_seen_turn = 4
    world.commit()
    assert world.get(Character, aria.id).traits == ["leal", "corajosa"]
    assert world.get(Character, aria.id).last_seen_turn == 4

    # List (scoped to session) + delete
    assert [c.name for c in world.list(Character, SESSION)] == ["Aria"]
    world.delete(fetched)
    world.commit()
    assert world.get(Character, aria.id) is None
    assert world.list(Character, SESSION) == []


def test_location_crud(world: WorldState) -> None:
    loc = world.add(
        Location(session_id=SESSION, name="Aldrath", description="castelo", first_visited_turn=1)
    )
    world.commit()
    assert world.get(Location, loc.id).description == "castelo"
    world.delete(loc)
    world.commit()
    assert world.list(Location, SESSION) == []


def test_relation_crud(world: WorldState) -> None:
    a = world.add(Character(session_id=SESSION, name="Aria", first_appeared_turn=1, last_seen_turn=1))
    b = world.add(Character(session_id=SESSION, name="Vex", first_appeared_turn=1, last_seen_turn=1))
    world.commit()

    rel = world.add(
        Relation(
            session_id=SESSION,
            a_character_id=a.id,
            b_character_id=b.id,
            kind="rivalry",
            valence=-2,
            since_turn=3,
        )
    )
    world.commit()
    fetched = world.get(Relation, rel.id)
    assert fetched.kind == "rivalry"
    assert fetched.valence == -2

    fetched.valence = -1
    world.commit()
    assert world.get(Relation, rel.id).valence == -1


def test_story_beat_crud(world: WorldState) -> None:
    beat = world.add(
        StoryBeat(
            session_id=SESSION,
            summary="Aria descobre a traição de Vex",
            turn=3,
            importance=8,
            tags=["traição", "reviravolta"],
        )
    )
    world.commit()
    fetched = world.get(StoryBeat, beat.id)
    assert fetched.importance == 8
    assert fetched.tags == ["traição", "reviravolta"]

    world.delete(fetched)
    world.commit()
    assert world.list(StoryBeat, SESSION) == []


def test_list_is_scoped_by_session(world: WorldState) -> None:
    world.add(Character(session_id="A", name="X", first_appeared_turn=1, last_seen_turn=1))
    world.add(Character(session_id="B", name="Y", first_appeared_turn=1, last_seen_turn=1))
    world.commit()
    assert [c.name for c in world.list(Character, "A")] == ["X"]
    assert [c.name for c in world.list(Character, "B")] == ["Y"]
