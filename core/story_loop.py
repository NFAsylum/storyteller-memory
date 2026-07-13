"""Turn manager. v1 (S1.3): input -> LLM -> store. v2 (S2.4): + retrieval + reflection.

The LLM is injected as an LlmClient Protocol, so the loop runs identically on the
deterministic FakeLlmClient (Sprints 1-2) and the real AnthropicLlmClient (Sprint 3+).
retrieval_policy and reflection are optional: without them run_turn behaves like v1
(empty context bundle, no consolidation), which keeps the S1.3 path working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.llm_client import LlmClient
from core.memory.mem0_adapter import Mem0Adapter
from core.memory.reflection import Reflection
from core.memory.retrieval_policy import ContextBundle, RetrievalPolicy
from core.session_config import SessionConfig, max_tokens_for, prompt_directives

_PROMPT_PATH = Path(__file__).parent / "prompts" / "story_continuation.txt"
_EMPTY_SLOT = "(none yet)"
# Consolidate every 2 turns so the Memory Inspector populates early (audit 0.1): a
# user who writes 3 turns must see characters/beats, not empty tabs. Was 5.
DEFAULT_REFLECT_EVERY = 2


@dataclass(frozen=True)
class TurnResult:
    narrator_text: str
    retrieved_context: dict[str, Any]
    stored_memory_ids: list[str] = field(default_factory=list)
    cost_usd: float = 0.0


def load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _slot(items: list[str], sep: str) -> str:
    return sep.join(i for i in items if i) or _EMPTY_SLOT


def render_prompt(
    template: str,
    bundle: ContextBundle | None,
    user_input: str,
    config: SessionConfig | None = None,
) -> str:
    """Fill the story-continuation template from a context bundle + narrative config."""
    directives = prompt_directives(config or SessionConfig())
    if bundle is None:
        active_characters = story_beats = raw_memories = _EMPTY_SLOT
    else:
        active_characters = _slot(bundle.active_characters, ", ")
        story_beats = _slot(bundle.structured_facts, "; ")
        raw_memories = _slot(bundle.raw_memories, "\n")
    return template.format(
        active_characters=active_characters,
        recent_locations=_EMPTY_SLOT,  # location NER not wired yet
        story_beats=story_beats,
        raw_memories=raw_memories,
        user_input=user_input,
        genre=directives["genre"],
        tone=directives["tone"],
        pov=directives["pov"],
        target_length=directives["target_length"],
        content_intensity=directives["content_intensity"],
        protagonist=directives["protagonist"],
    )


class StoryLoop:
    """Coordinates a narrative turn: retrieve context, narrate, store, periodically reflect."""

    def __init__(
        self,
        session_id: str,
        memory: Mem0Adapter,
        llm: LlmClient,
        *,
        retrieval_policy: RetrievalPolicy | None = None,
        reflection: Reflection | None = None,
        reflect_every: int = DEFAULT_REFLECT_EVERY,
        prompt_template: str | None = None,
        start_turn: int = 0,
        config: SessionConfig | None = None,
    ) -> None:
        self.session_id = session_id
        self.memory = memory
        self.llm = llm
        self.retrieval_policy = retrieval_policy
        self.reflection = reflection
        self.reflect_every = reflect_every
        self._prompt_template = prompt_template or load_prompt_template()
        self._turn = start_turn  # resume numbering for a persisted session
        self.config = config or SessionConfig()

    def run_turn(self, user_input: str) -> TurnResult:
        self._turn += 1
        bundle = (
            self.retrieval_policy.build_context(self.session_id, self._turn, user_input)
            if self.retrieval_policy
            else None
        )
        prompt = self._render_prompt(user_input, bundle)
        response = self.llm.generate(
            system=prompt,
            messages=[{"role": "user", "content": user_input}],
            max_tokens=max_tokens_for(self.config),
        )
        narrator_text = response.content

        stored_memory_ids: list[str] = []
        memory_id = self.memory.add(
            self._turn_record(user_input, narrator_text),
            metadata={"turn": self._turn, "type": "story_turn"},
        )
        if memory_id:
            stored_memory_ids.append(memory_id)

        self._maybe_reflect()

        return TurnResult(
            narrator_text=narrator_text,
            retrieved_context=self._context_dict(bundle),
            stored_memory_ids=stored_memory_ids,
            cost_usd=response.cost_usd,
        )

    def _render_prompt(self, user_input: str, bundle: ContextBundle | None) -> str:
        return render_prompt(self._prompt_template, bundle, user_input, self.config)

    def _maybe_reflect(self) -> None:
        if self.reflection and self._turn % self.reflect_every == 0:
            self.reflection.consolidate(self.session_id, since_turn=self._turn - self.reflect_every)

    def _context_dict(self, bundle: ContextBundle | None) -> dict[str, Any]:
        if bundle is None:
            return {"raw_memories": [], "active_characters": [], "turn": self._turn}
        return {**bundle.model_dump(), "turn": self._turn}

    def _turn_record(self, user_input: str, narrator_text: str) -> str:
        return f"Turn {self._turn}\nPlayer: {user_input}\nNarrator: {narrator_text}"
