"""RetrievalPolicy — assembles the context bundle injected into the next turn's prompt.

Default strategy: top-K mem0 memories by similarity to the user input, the top story
beats by importance, and the characters seen within the recent-turns window. Location
NER over the user input is deferred (there's no bundle slot for it yet).
"""

from __future__ import annotations

from pydantic import BaseModel

from core.memory.mem0_adapter import Mem0Adapter
from core.memory.world_state import WorldState

DEFAULT_TOP_MEMORIES = 5
DEFAULT_TOP_BEATS = 3
DEFAULT_RECENT_TURNS = 10
_CHARS_PER_TOKEN = 4  # project-wide approximation


class ContextBundle(BaseModel):
    raw_memories: list[str]
    structured_facts: list[str]
    active_characters: list[str]
    token_estimate: int


class RetrievalPolicy:
    def __init__(
        self,
        memory: Mem0Adapter,
        world_state: WorldState,
        *,
        top_memories: int = DEFAULT_TOP_MEMORIES,
        top_beats: int = DEFAULT_TOP_BEATS,
        recent_turns: int = DEFAULT_RECENT_TURNS,
    ) -> None:
        self._memory = memory
        self._world = world_state
        self._top_memories = top_memories
        self._top_beats = top_beats
        self._recent_turns = recent_turns

    def build_context(self, session_id: str, current_turn: int, user_input: str) -> ContextBundle:
        raw_memories = [m.text for m in self._memory.search(user_input, top_k=self._top_memories)]
        structured_facts = [b.summary for b in self._world.top_beats(session_id, self._top_beats)]
        min_turn = max(0, current_turn - self._recent_turns)
        active_characters = [c.name for c in self._world.active_characters(session_id, min_turn)]

        return ContextBundle(
            raw_memories=raw_memories,
            structured_facts=structured_facts,
            active_characters=active_characters,
            token_estimate=self._estimate_tokens(
                raw_memories, structured_facts, active_characters, [user_input]
            ),
        )

    @staticmethod
    def _estimate_tokens(*text_lists: list[str]) -> int:
        total_chars = sum(len(text) for text_list in text_lists for text in text_list)
        return total_chars // _CHARS_PER_TOKEN
