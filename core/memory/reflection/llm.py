"""LlmReflection — real reflection: the configured LLM summarizes turns into JSON.

The LLM (local or Anthropic) returns structured facts matching `ReflectionExtraction`;
malformed replies are retried, and a persistent failure is logged and reported via
`ReflectionResult.failed` (F1.6) rather than silently swallowed. The DB-write half
lives in `persist.py`; the JSON shapes in `schema.py`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from core.llm_client import LlmClient
from core.memory.mem0_adapter import Mem0Adapter, MemoryRecord
from core.memory.reflection.persist import (
    persist_beats,
    persist_characters,
    persist_locations,
    persist_relations,
)
from core.memory.reflection.protocol import ReflectionResult, _already_consolidated, _player_input
from core.memory.reflection.schema import ReflectionExtraction
from core.memory.world_state import Character, Location, Relation, WorldState

logger = logging.getLogger(__name__)

# reflection/ is one level deeper than the old module, so climb three parents to core/.
_REFLECTION_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "reflection.txt"
_DEFAULT_MAX_RETRIES = 2


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
        if _already_consolidated(self._world, session_id, last_turn):
            return ReflectionResult(beats_created=0, characters_updated=0, relations_updated=0, cost_usd=0.0)

        prompt = self._build_prompt(session_id, turns)
        extraction, cost = self._extract_with_retry(prompt)
        if extraction is None:
            # Couldn't get valid JSON after retries — persist nothing, still report cost + failure.
            return ReflectionResult(
                beats_created=0, characters_updated=0, relations_updated=0, cost_usd=cost, failed=True
            )

        characters_updated = persist_characters(self._world, session_id, extraction, last_turn)
        persist_locations(self._world, session_id, extraction)
        relations_updated = persist_relations(self._world, session_id, extraction, last_turn)
        beats_created = persist_beats(self._world, session_id, extraction, last_turn)
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
        last_content = ""
        attempts = self._max_retries + 1
        for _ in range(attempts):
            response = self._llm.generate(system=prompt, messages=messages)
            cost += response.cost_usd
            last_content = response.content
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
        logger.error(
            "LlmReflection: all %d attempts failed to produce valid JSON. Last response: %s",
            attempts,
            last_content[:500],
        )
        return None, cost

    def _build_prompt(self, session_id: str, turns: list[MemoryRecord]) -> str:
        turns_text = "\n".join(
            f"Turn {r.metadata.get('turn', '?')}: {_player_input(r.text)}" for r in turns
        )
        known_chars = ", ".join(c.name for c in self._world.list(Character, session_id)) or "none"
        known_locs = ", ".join(loc.name for loc in self._world.list(Location, session_id)) or "none"
        known_rels = ", ".join(r.kind for r in self._world.list(Relation, session_id)) or "none"
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
