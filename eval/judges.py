"""LLM-as-judge for recall and hallucination detection (eval).

The subjective judges (consistency) arrive in Sprint 4; here we cover recall
(YES/NO/PARTIAL) and hallucination (bool), both via the configured LLM.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from core.llm_client import LlmClient
from eval.scenario import Question

_PROMPT_DIR = Path(__file__).parent / "prompts"
RecallVerdict = Literal["YES", "NO", "PARTIAL"]
_JUDGE_TRIGGER = "Judge now. Output only the single word."


def _load(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


def _parse_recall(text: str) -> RecallVerdict:
    for token in text.upper().replace(".", " ").split():
        if token in ("YES", "NO", "PARTIAL"):
            return token  # type: ignore[return-value]
    upper = text.upper()
    if "PARTIAL" in upper:
        return "PARTIAL"
    if "YES" in upper:
        return "YES"
    return "NO"  # conservative default


def _parse_yes(text: str) -> bool:
    for token in text.upper().replace(".", " ").split():
        if token == "YES":
            return True
        if token == "NO":
            return False
    return "YES" in text.upper()


def _parse_score(text: str) -> float:
    """Extract a [0,1] consistency score from the reply; clamp; default 0.0."""
    match = re.search(r"\d*\.?\d+", text)
    if match is None:
        return 0.0
    try:
        value = float(match.group())
    except ValueError:
        return 0.0
    return max(0.0, min(1.0, value))


class LlmJudge:
    """Recall + hallucination judging via the configured LLM (local or Anthropic)."""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm
        self._recall_template = _load("judge_recall.txt")
        self._hallucination_template = _load("judge_hallucination.txt")
        self._consistency_template = _load("judge_consistency.txt")

    def judge_recall(self, question: Question, response: str) -> RecallVerdict:
        prompt = self._recall_template.format(
            ground_truth=question.ground_truth,
            acceptable_variants=", ".join(question.acceptable_variants) or "(none)",
            response_text=response,
        )
        reply = self._llm.generate(system=prompt, messages=[{"role": "user", "content": _JUDGE_TRIGGER}])
        return _parse_recall(reply.content)

    def judge_hallucination(self, ground_truth: str, response: str) -> bool:
        prompt = self._hallucination_template.format(ground_truth=ground_truth, response_text=response)
        reply = self._llm.generate(system=prompt, messages=[{"role": "user", "content": _JUDGE_TRIGGER}])
        return _parse_yes(reply.content)

    def judge_consistency(self, character_profile: dict[str, Any], response: str) -> float:
        """Rate [0,1] how well the response respects the character profile.

        Calibration against human scores (the >80%-agreement gate) is deferred until
        Marco provides reference scores — see S4.2 in docs/tasks.md.
        """
        prompt = self._consistency_template.format(
            character_name=character_profile.get("name", ""),
            traits=", ".join(character_profile.get("traits", [])) or "(none)",
            relations=", ".join(character_profile.get("relations", [])) or "(none)",
            backstory=character_profile.get("backstory", "") or "(none)",
            response_text=response,
        )
        reply = self._llm.generate(
            system=prompt, messages=[{"role": "user", "content": "Score now. One decimal, nothing else."}]
        )
        return _parse_score(reply.content)
