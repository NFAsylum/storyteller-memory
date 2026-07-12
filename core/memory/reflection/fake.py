"""FakeReflection — deterministic, mechanical consolidation into world_state.

The real LLM-driven impl lives in `llm.py`; here FakeReflection uses crude
mechanical rules so the whole pipeline is exercised without an API:

    - character: any capitalized word appearing more than twice across the player inputs
    - location:  a "castelo/reino/cidade/... de <ProperNoun>" phrase
    - relation:  a co-occurrence link between the two most-frequent characters

It is deliberately dumb — Sprint 3 measures how much a real LLM improves on this.
"""

from __future__ import annotations

import re
from collections import Counter

from core.memory.mem0_adapter import Mem0Adapter, MemoryRecord
from core.memory.reflection.protocol import (
    ReflectionResult,
    _already_consolidated,
    _player_input,
)
from core.memory.world_state import Character, Location, Relation, StoryBeat, WorldState

# A capitalized token (accented letters included), 3+ chars to skip "O"/"A"/"Um".
_WORD_RE = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]{2,}\b")
# "<place-word> de <ProperNoun>" — place word is case-insensitive, the noun is not.
_LOCATION_RE = re.compile(r"(?i:castelo|reino|cidade|vila|forte|torre|porto)\s+de\s+([A-ZÀ-Ý][a-zà-ÿ]{2,})")
_COOCCURRENCE = "co-ocorrencia"
# Structural labels and a few common Portuguese sentence-starters that aren't names.
_STOPWORDS = frozenset(
    {
        "Turn",
        "Player",
        "Narrator",
        "Nas",
        "Nos",
        "Aos",
        "Uma",
        "Uns",
        "Numa",
        "Ele",
        "Ela",
        "Eles",
        "Elas",
        "Depois",
        "Quando",
        "Enquanto",
        "Ainda",
    }
)
_CANDIDATE_MIN_COUNT = 2  # strictly more than this ("> 2x")


class FakeReflection:
    """Deterministic, mechanical reflection into world_state (characters/locations/relations/beats)."""

    def __init__(self, world_state: WorldState, memory: Mem0Adapter) -> None:
        self._world = world_state
        self._memory = memory

    def consolidate(self, session_id: str, since_turn: int) -> ReflectionResult:
        turns = sorted(
            (r for r in self._memory.list_all() if r.metadata.get("turn", 0) > since_turn),
            key=lambda r: r.metadata.get("turn", 0),
        )
        if not turns:
            return ReflectionResult(
                beats_created=0, characters_updated=0, relations_updated=0, cost_usd=0.0
            )

        first_turn = int(turns[0].metadata.get("turn", since_turn + 1))
        last_turn = int(turns[-1].metadata.get("turn", since_turn + 1))

        if _already_consolidated(self._world, session_id, last_turn):
            return ReflectionResult(beats_created=0, characters_updated=0, relations_updated=0, cost_usd=0.0)

        counts = self._character_counts(turns)
        candidates = sorted(name for name, count in counts.items() if count > _CANDIDATE_MIN_COUNT)
        characters_updated = self._upsert_characters(session_id, candidates, first_turn, last_turn)
        self._extract_locations(session_id, turns, first_turn)
        relations_updated = self._link_top_characters(session_id, candidates, counts, last_turn)

        self._world.add(
            StoryBeat(
                session_id=session_id,
                summary=f"Consolidated turns {first_turn}-{last_turn}: {len(candidates)} character(s)",
                turn=last_turn,
                importance=min(10, 1 + len(candidates)),
                tags=[],
            )
        )
        self._world.commit()

        return ReflectionResult(
            beats_created=1,
            characters_updated=characters_updated,
            relations_updated=relations_updated,
            cost_usd=0.0,
        )

    def _upsert_characters(
        self, session_id: str, candidates: list[str], first_turn: int, last_turn: int
    ) -> int:
        existing = {c.name: c for c in self._world.list(Character, session_id)}
        for name in candidates:
            if name in existing:
                existing[name].last_seen_turn = last_turn  # update, never duplicate
            else:
                self._world.add(
                    Character(
                        session_id=session_id,
                        name=name,
                        traits=[],
                        first_appeared_turn=first_turn,
                        last_seen_turn=last_turn,
                    )
                )
        return len(candidates)

    def _extract_locations(self, session_id: str, turns: list[MemoryRecord], first_turn: int) -> int:
        existing = {loc.name for loc in self._world.list(Location, session_id)}
        names: set[str] = set()
        for record in turns:
            names.update(_LOCATION_RE.findall(self._player_input(record.text)))
        created = 0
        for name in sorted(names):
            if name not in existing:
                self._world.add(
                    Location(
                        session_id=session_id, name=name, description="", first_visited_turn=first_turn
                    )
                )
                existing.add(name)
                created += 1
        return created

    def _link_top_characters(
        self, session_id: str, candidates: list[str], counts: Counter[str], last_turn: int
    ) -> int:
        if len(candidates) < 2:
            return 0
        ranked = sorted(candidates, key=lambda name: (-counts[name], name))
        by_name = {c.name: c for c in self._world.list(Character, session_id)}
        a, b = by_name.get(ranked[0]), by_name.get(ranked[1])
        if a is None or b is None or self._relation_exists(session_id, a.id, b.id):
            return 0
        self._world.add(
            Relation(
                session_id=session_id,
                a_character_id=a.id,
                b_character_id=b.id,
                kind=_COOCCURRENCE,
                valence=0,
                since_turn=last_turn,
            )
        )
        return 1

    def _relation_exists(self, session_id: str, a_id: int, b_id: int) -> bool:
        return any(
            {r.a_character_id, r.b_character_id} == {a_id, b_id} and r.kind == _COOCCURRENCE
            for r in self._world.list(Relation, session_id)
        )

    def _character_counts(self, turns: list[MemoryRecord]) -> Counter[str]:
        counts: Counter[str] = Counter()
        for record in turns:
            for word in _WORD_RE.findall(self._player_input(record.text)):
                if word not in _STOPWORDS:
                    counts[word] += 1
        return counts

    @staticmethod
    def _player_input(text: str) -> str:
        return _player_input(text)
