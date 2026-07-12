"""Write a validated ReflectionExtraction into world_state.

These functions are the DB-write half of LlmReflection, split out so `llm.py`
keeps only the LLM call + parse orchestration. Each is idempotent-ish: it skips
characters/locations/relations that already exist for the session.
"""

from __future__ import annotations

from core.memory.reflection.schema import ReflectionExtraction
from core.memory.world_state import Character, Location, Relation, StoryBeat, WorldState


def persist_characters(
    world: WorldState, session_id: str, extraction: ReflectionExtraction, last_turn: int
) -> int:
    existing = {c.name: c for c in world.list(Character, session_id)}
    updated = 0
    for new_char in extraction.new_characters:
        if new_char.name in existing:
            existing[new_char.name].last_seen_turn = last_turn
        else:
            created = world.add(
                Character(
                    session_id=session_id,
                    name=new_char.name,
                    traits=new_char.traits,
                    first_appeared_turn=new_char.first_appeared_turn or last_turn,
                    last_seen_turn=last_turn,
                )
            )
            existing[new_char.name] = created
        updated += 1
    for change in extraction.character_updates:
        character = existing.get(change.name)
        if character is not None:
            character.traits = sorted(set(character.traits) | set(change.new_traits))
            character.last_seen_turn = last_turn
            updated += 1
    return updated


def persist_locations(world: WorldState, session_id: str, extraction: ReflectionExtraction) -> int:
    existing = {loc.name for loc in world.list(Location, session_id)}
    created = 0
    for loc in extraction.new_locations:
        if loc.name not in existing:
            world.add(
                Location(
                    session_id=session_id,
                    name=loc.name,
                    description=loc.description,
                    first_visited_turn=loc.first_visited_turn or 1,
                )
            )
            existing.add(loc.name)
            created += 1
    return created


def persist_relations(
    world: WorldState, session_id: str, extraction: ReflectionExtraction, last_turn: int
) -> int:
    by_name = {c.name: c for c in world.list(Character, session_id)}
    created = 0
    for rel in extraction.relations:
        a, b = by_name.get(rel.a), by_name.get(rel.b)
        if a is None or b is None:
            continue  # skip relations referencing unknown characters
        if any(
            {r.a_character_id, r.b_character_id} == {a.id, b.id} and r.kind == rel.kind
            for r in world.list(Relation, session_id)
        ):
            continue
        world.add(
            Relation(
                session_id=session_id,
                a_character_id=a.id,
                b_character_id=b.id,
                kind=rel.kind,
                valence=rel.valence,
                since_turn=rel.since_turn or last_turn,
            )
        )
        created += 1
    return created


def persist_beats(
    world: WorldState, session_id: str, extraction: ReflectionExtraction, last_turn: int
) -> int:
    for beat in extraction.beats:
        world.add(
            StoryBeat(
                session_id=session_id,
                summary=beat.summary,
                turn=beat.turn or last_turn,
                importance=beat.importance,
                tags=beat.tags,
            )
        )
    return len(extraction.beats)
