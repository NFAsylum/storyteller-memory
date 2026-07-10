"""Reflection Protocol + FakeReflection.

Reflection consolidates the last N turns into structured world_state. The real
LLM-driven impl (AnthropicReflection) arrives in Sprint 3; here FakeReflection uses a
crude mechanical rule so the whole pipeline is exercised without an API:

    any capitalized word appearing more than twice across the turns' player inputs
    becomes a character candidate.

It is deliberately dumb — Sprint 3 measures how much a real LLM improves on this.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.memory.mem0_adapter import Mem0Adapter, MemoryRecord
from core.memory.world_state import Character, StoryBeat, WorldState

# A capitalized token (accented letters included), 3+ chars to skip "O"/"A"/"Um".
_WORD_RE = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]{2,}\b")
_PLAYER_PREFIX = "Player:"
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


class ReflectionResult(BaseModel):
    beats_created: int = Field(ge=0)
    characters_updated: int = Field(ge=0)
    relations_updated: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


@runtime_checkable
class Reflection(Protocol):
    def consolidate(self, session_id: str, since_turn: int) -> ReflectionResult: ...


class FakeReflection:
    """Deterministic, mechanical reflection: capitalized-word frequency -> characters."""

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
        candidates = self._character_candidates(turns)

        existing = {c.name: c for c in self._world.list(Character, session_id)}
        characters_updated = 0
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
            characters_updated += 1

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
            relations_updated=0,  # relation inference is out of scope for the Fake rule
            cost_usd=0.0,
        )

    def _character_candidates(self, turns: list[MemoryRecord]) -> list[str]:
        counts: Counter[str] = Counter()
        for record in turns:
            for word in _WORD_RE.findall(self._player_input(record.text)):
                if word not in _STOPWORDS:
                    counts[word] += 1
        # sorted for deterministic ordering
        return sorted(name for name, count in counts.items() if count > _CANDIDATE_MIN_COUNT)

    @staticmethod
    def _player_input(text: str) -> str:
        # Read only the "Player:" line so narration filler and labels don't pollute names.
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(_PLAYER_PREFIX):
                return stripped[len(_PLAYER_PREFIX) :].strip()
        return text
