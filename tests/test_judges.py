"""Tests for eval.judges — LLM mocked, 3 cases per judge (keyless)."""

from unittest.mock import MagicMock

import pytest

from core.llm_client import LlmResponse
from eval.judges import LlmJudge
from eval.scenario import Question

_Q = Question(
    id="q1",
    asked_after_turn=5,
    category="recall_factual",
    question="Quem descobriu a traição?",
    ground_truth="Aria",
    acceptable_variants=["a cavaleira Aria"],
)


def _judge_returning(text: str) -> LlmJudge:
    llm = MagicMock()
    llm.generate.return_value = LlmResponse(
        content=text, stop_reason="stop", usage={"input_tokens": 10, "output_tokens": 1}, cost_usd=0.0
    )
    return LlmJudge(llm)


@pytest.mark.parametrize(
    ("reply", "expected"),
    [("YES", "YES"), ("NO", "NO"), ("PARTIAL", "PARTIAL"), ("The verdict is PARTIAL.", "PARTIAL")],
)
def test_judge_recall_parses_verdict(reply: str, expected: str) -> None:
    assert _judge_returning(reply).judge_recall(_Q, "some response") == expected


@pytest.mark.parametrize(
    ("reply", "expected"),
    [("YES", True), ("NO", False), ("No, it is consistent.", False)],
)
def test_judge_hallucination_parses_bool(reply: str, expected: bool) -> None:
    assert _judge_returning(reply).judge_hallucination("Aria", "some response") is expected


def test_judge_recall_fills_prompt_with_ground_truth() -> None:
    llm = MagicMock()
    llm.generate.return_value = LlmResponse(
        content="YES", stop_reason="stop", usage={"input_tokens": 1, "output_tokens": 1}, cost_usd=0.0
    )
    LlmJudge(llm).judge_recall(_Q, "Foi Aria.")

    _, kwargs = llm.generate.call_args
    assert "Aria" in kwargs["system"]  # ground_truth injected
    assert "Foi Aria." in kwargs["system"]  # response injected
