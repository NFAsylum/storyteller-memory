"""Reflection Protocol + FakeReflection.

Reflection consolidates the last N turns into structured world_state. The real
LLM-driven impl (AnthropicReflection) arrives in Sprint 3; here FakeReflection uses
crude mechanical rules so the whole pipeline is exercised without an API:

    - character: any capitalized word appearing more than twice across the player inputs
    - location:  a "castelo/reino/cidade/... de <ProperNoun>" phrase
    - relation:  a co-occurrence link between the two most-frequent characters

It is deliberately dumb — Sprint 3 measures how much a real LLM improves on this.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, ValidationError

from core.llm_client import LlmClient
from core.memory.mem0_adapter import Mem0Adapter, MemoryRecord
from core.memory.world_state import Character, Location, Relation, StoryBeat, WorldState

_REFLECTION_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "reflection.txt"
_DEFAULT_MAX_RETRIES = 2

# A capitalized token (accented letters included), 3+ chars to skip "O"/"A"/"Um".
_WORD_RE = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]{2,}\b")
# "<place-word> de <ProperNoun>" — place word is case-insensitive, the noun is not.
_LOCATION_RE = re.compile(r"(?i:castelo|reino|cidade|vila|forte|torre|porto)\s+de\s+([A-ZÀ-Ý][a-zà-ÿ]{2,})")
_PLAYER_PREFIX = "Player:"
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


class ReflectionResult(BaseModel):
    beats_created: int = Field(ge=0)
    characters_updated: int = Field(ge=0)
    relations_updated: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


@runtime_checkable
class Reflection(Protocol):
    def consolidate(self, session_id: str, since_turn: int) -> ReflectionResult: ...


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


def _player_input(text: str) -> str:
    # Read only the "Player:" line so narration filler and labels don't pollute extraction.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_PLAYER_PREFIX):
            return stripped[len(_PLAYER_PREFIX) :].strip()
    return text


# --- Real LLM reflection (Sprint 3) ------------------------------------------------


class _ExtractedCharacter(BaseModel):
    name: str
    traits: list[str] = Field(default_factory=list)
    first_appeared_turn: int = 0


class _CharacterUpdate(BaseModel):
    name: str
    new_traits: list[str] = Field(default_factory=list)
    evidence_turn: int = 0


class _ExtractedLocation(BaseModel):
    name: str
    description: str = ""
    first_visited_turn: int = 0


class _ExtractedRelation(BaseModel):
    a: str
    b: str
    kind: str
    valence: int = 0
    since_turn: int = 0


class _ExtractedBeat(BaseModel):
    summary: str
    importance: int = 1
    turn: int = 0
    tags: list[str] = Field(default_factory=list)


class ReflectionExtraction(BaseModel):
    """Structured facts the LLM returns; lenient (ignores unexpected keys)."""

    new_characters: list[_ExtractedCharacter] = Field(default_factory=list)
    character_updates: list[_CharacterUpdate] = Field(default_factory=list)
    new_locations: list[_ExtractedLocation] = Field(default_factory=list)
    relations: list[_ExtractedRelation] = Field(default_factory=list)
    beats: list[_ExtractedBeat] = Field(default_factory=list)


def _parse_json_object(text: str) -> dict[str, Any]:
    """Extract the outermost JSON object from a model reply (tolerates fences/prose)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in reply")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("top-level JSON is not an object")
    return parsed


class LlmReflection:
    """Real reflection: the configured LLM (local or Anthropic) summarizes turns to JSON."""

    def __init__(
        self,
        llm: LlmClient,
        world_state: WorldState,
        memory: Mem0Adapter,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        prompt_template: str | None = None,
    ) -> None:
        self._llm = llm
        self._world = world_state
        self._memory = memory
        self._max_retries = max_retries
        self._template = prompt_template or _REFLECTION_PROMPT_PATH.read_text(encoding="utf-8")

    def consolidate(self, session_id: str, since_turn: int) -> ReflectionResult:
        turns = sorted(
            (r for r in self._memory.list_all() if r.metadata.get("turn", 0) > since_turn),
            key=lambda r: r.metadata.get("turn", 0),
        )
        if not turns:
            return ReflectionResult(
                beats_created=0, characters_updated=0, relations_updated=0, cost_usd=0.0
            )

        last_turn = int(turns[-1].metadata.get("turn", since_turn + 1))
        prompt = self._build_prompt(session_id, turns)
        extraction, cost = self._extract_with_retry(prompt)
        if extraction is None:
            # Couldn't get valid JSON after retries — persist nothing, still report cost.
            return ReflectionResult(
                beats_created=0, characters_updated=0, relations_updated=0, cost_usd=cost
            )

        characters_updated = self._persist_characters(session_id, extraction, last_turn)
        self._persist_locations(session_id, extraction)
        relations_updated = self._persist_relations(session_id, extraction, last_turn)
        beats_created = self._persist_beats(session_id, extraction, last_turn)
        self._world.commit()

        return ReflectionResult(
            beats_created=beats_created,
            characters_updated=characters_updated,
            relations_updated=relations_updated,
            cost_usd=cost,
        )

    def _extract_with_retry(self, prompt: str) -> tuple[ReflectionExtraction | None, float]:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": "Extract the structured facts as JSON now."}
        ]
        cost = 0.0
        for _ in range(self._max_retries + 1):
            response = self._llm.generate(system=prompt, messages=messages)
            cost += response.cost_usd
            try:
                return ReflectionExtraction.model_validate(_parse_json_object(response.content)), cost
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "user",
                        "content": f"That was not valid JSON matching the schema ({exc}). "
                        "Return ONLY the JSON object, no prose, no code fences.",
                    }
                )
        return None, cost

    def _build_prompt(self, session_id: str, turns: list[MemoryRecord]) -> str:
        turns_text = "\n".join(
            f"Turn {r.metadata.get('turn', '?')}: {_player_input(r.text)}" for r in turns
        )
        known_chars = ", ".join(c.name for c in self._world.list(Character, session_id)) or "none"
        known_locs = ", ".join(loc.name for loc in self._world.list(Location, session_id)) or "none"
        known_rels = (
            ", ".join(r.kind for r in self._world.list(Relation, session_id)) or "none"
        )
        # reflection.txt contains literal JSON braces, so substitute by replace(), not format().
        prompt = self._template
        for token, value in (
            ("{n}", str(len(turns))),
            ("{turns_text}", turns_text),
            ("{known_characters}", known_chars),
            ("{known_locations}", known_locs),
            ("{recent_relations}", known_rels),
        ):
            prompt = prompt.replace(token, value)
        return prompt

    def _persist_characters(
        self, session_id: str, extraction: ReflectionExtraction, last_turn: int
    ) -> int:
        existing = {c.name: c for c in self._world.list(Character, session_id)}
        updated = 0
        for new_char in extraction.new_characters:
            if new_char.name in existing:
                existing[new_char.name].last_seen_turn = last_turn
            else:
                created = self._world.add(
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

    def _persist_locations(self, session_id: str, extraction: ReflectionExtraction) -> int:
        existing = {loc.name for loc in self._world.list(Location, session_id)}
        created = 0
        for loc in extraction.new_locations:
            if loc.name not in existing:
                self._world.add(
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

    def _persist_relations(
        self, session_id: str, extraction: ReflectionExtraction, last_turn: int
    ) -> int:
        by_name = {c.name: c for c in self._world.list(Character, session_id)}
        created = 0
        for rel in extraction.relations:
            a, b = by_name.get(rel.a), by_name.get(rel.b)
            if a is None or b is None:
                continue  # skip relations referencing unknown characters
            if any(
                {r.a_character_id, r.b_character_id} == {a.id, b.id} and r.kind == rel.kind
                for r in self._world.list(Relation, session_id)
            ):
                continue
            self._world.add(
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

    def _persist_beats(
        self, session_id: str, extraction: ReflectionExtraction, last_turn: int
    ) -> int:
        for beat in extraction.beats:
            self._world.add(
                StoryBeat(
                    session_id=session_id,
                    summary=beat.summary,
                    turn=beat.turn or last_turn,
                    importance=beat.importance,
                    tags=beat.tags,
                )
            )
        return len(extraction.beats)
