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
DEFAULT_MEMORY_SCORE_THRESHOLD = 0.5  # drop weakly-related memories (T-REP.2)
_DUP_THRESHOLD = 0.6  # drop a raw memory that overlaps a structured fact (T-REP.3)
_CHARS_PER_TOKEN = 4  # project-wide approximation


def _overlap_ratio(a: str, b: str) -> float:
    """Word-set Jaccard between two short strings — a crude near-duplicate check."""
    aw, bw = set(a.lower().split()), set(b.lower().split())
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / len(aw | bw)


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
        score_threshold: float = DEFAULT_MEMORY_SCORE_THRESHOLD,
    ) -> None:
        self._memory = memory
        self._world = world_state
        self._top_memories = top_memories
        self._top_beats = top_beats
        self._recent_turns = recent_turns
        self._score_threshold = score_threshold

    def build_context(self, session_id: str, current_turn: int, user_input: str) -> ContextBundle:
        # T-REP.2: keep only memories similar enough to the input (a None score means the
        # backend didn't rank it — keep it rather than silently drop context).
        hits = self._memory.search(user_input, top_k=self._top_memories)
        raw_memories = [m.text for m in hits if m.score is None or m.score >= self._score_threshold]
        structured_facts = [b.summary for b in self._world.top_beats(session_id, self._top_beats)]
        # T-REP.3: drop a raw memory that just restates a structured fact (the model would
        # otherwise re-narrate the duplicated information).
        raw_memories = [
            r for r in raw_memories
            if all(_overlap_ratio(r, f) < _DUP_THRESHOLD for f in structured_facts)
        ]
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
