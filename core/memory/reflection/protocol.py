"""Reflection Protocol, result model, and helpers shared by the fake and LLM impls.

Reflection consolidates the last N turns into structured world_state. Two impls live
in sibling modules: FakeReflection (deterministic, mechanical) and LlmReflection
(the configured LLM). Both reuse `_already_consolidated` (idempotency guard, F1.3)
and `_player_input` (read only the player's line out of a stored turn).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.memory.world_state import StoryBeat, WorldState

_PLAYER_PREFIX = "Player:"


class ReflectionResult(BaseModel):
    beats_created: int = Field(ge=0)
    characters_updated: int = Field(ge=0)
    relations_updated: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    failed: bool = False  # True when the LLM never produced valid JSON (F1.6)


@runtime_checkable
class Reflection(Protocol):
    def consolidate(self, session_id: str, since_turn: int) -> ReflectionResult: ...


def _already_consolidated(world: WorldState, session_id: str, last_turn: int) -> bool:
    """True if a story beat already covers up to last_turn (dedupe re-runs — F1.3)."""
    beats = world.list(StoryBeat, session_id)
    return bool(beats) and max(b.turn for b in beats) >= last_turn


def _player_input(text: str) -> str:
    # Read only the "Player:" line so narration filler and labels don't pollute extraction.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_PLAYER_PREFIX):
            return stripped[len(_PLAYER_PREFIX) :].strip()
    return text
