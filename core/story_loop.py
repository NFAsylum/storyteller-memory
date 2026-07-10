"""Minimal turn manager (S1.3 v1): user input -> LLM narration -> store raw turn in mem0.

The LLM is injected as an LlmClient Protocol, so the loop runs identically on the
deterministic FakeLlmClient (Sprints 1-2) and the real AnthropicLlmClient (Sprint 3+).
No retrieval or world state yet — the prompt's world_state/memory slots are placeholders;
Sprint 2 wires in RetrievalPolicy and populates them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.llm_client import LlmClient
from core.memory.mem0_adapter import Mem0Adapter

_PROMPT_PATH = Path(__file__).parent / "prompts" / "story_continuation.txt"
_EMPTY_SLOT = "(none yet)"


@dataclass(frozen=True)
class TurnResult:
    narrator_text: str
    retrieved_context: dict[str, Any]
    stored_memory_ids: list[str] = field(default_factory=list)
    cost_usd: float = 0.0


def load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


class StoryLoop:
    """Coordinates a single narrative turn: narrate, then persist the turn to mem0."""

    def __init__(
        self,
        session_id: str,
        memory: Mem0Adapter,
        llm: LlmClient,
        *,
        prompt_template: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.memory = memory
        self.llm = llm
        self._prompt_template = prompt_template or load_prompt_template()
        self._turn = 0

    def run_turn(self, user_input: str) -> TurnResult:
        self._turn += 1
        # v1 context bundle is empty — no retrieval yet (Sprint 2).
        retrieved_context: dict[str, Any] = {
            "raw_memories": [],
            "active_characters": [],
            "turn": self._turn,
        }
        prompt = self._prompt_template.format(
            active_characters=_EMPTY_SLOT,
            recent_locations=_EMPTY_SLOT,
            story_beats=_EMPTY_SLOT,
            raw_memories=_EMPTY_SLOT,
            user_input=user_input,
        )
        response = self.llm.generate(
            system=prompt,
            messages=[{"role": "user", "content": user_input}],
        )
        narrator_text = response.content

        stored_memory_ids: list[str] = []
        memory_id = self.memory.add(
            self._turn_record(user_input, narrator_text),
            metadata={"turn": self._turn, "type": "story_turn"},
        )
        if memory_id:
            stored_memory_ids.append(memory_id)

        return TurnResult(
            narrator_text=narrator_text,
            retrieved_context=retrieved_context,
            stored_memory_ids=stored_memory_ids,
            cost_usd=response.cost_usd,
        )

    def _turn_record(self, user_input: str, narrator_text: str) -> str:
        return f"Turn {self._turn}\nPlayer: {user_input}\nNarrator: {narrator_text}"
