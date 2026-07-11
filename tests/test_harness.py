"""Tests for eval.harness — one mini-scenario with FakeLlm (fast, deterministic, keyless)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.llm_fakes import FakeLlmClient
from core.memory.mem0_adapter import MemoryRecord
from core.memory.world_state import Base, WorldState
from eval.harness import HarnessConfig, ScenarioResult, run_scenario, simple_recall_judge
from eval.scenario import Question, Scenario, Scene

SESSION = "harness-test"


class _FakeMem0:
    session_id = SESSION

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []
        self._n = 0

    def add(self, text: str, metadata: dict | None = None) -> str:
        self._n += 1
        rid = f"m{self._n}"
        self._records.append(MemoryRecord(id=rid, text=text, metadata=metadata or {}))
        return rid

    def search(self, query: str, top_k: int = 5) -> list[MemoryRecord]:
        return self._records[-top_k:]

    def list_all(self) -> list[MemoryRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


def _q(qid: str, question: str, ground_truth: str) -> Question:
    return Question(
        id=qid,
        asked_after_turn=2,
        category="recall_factual",
        question=question,
        ground_truth=ground_truth,
        acceptable_variants=[],
    )


# FakeLlm echoes the user message (the question) into its reply, so a ground_truth that
# appears in the question text scores a recall hit — deterministic and predictable.
_MINI = Scenario(
    id="mini-01",
    scenes=[
        Scene(turn_id=1, user_input="Aria chega ao castelo."),
        Scene(turn_id=2, user_input="Vex esconde a carta."),
    ],
    questions=[
        _q("q1", "O que Aria faz no castelo?", "Aria"),  # 'Aria' is in the question -> hit
        _q("q2", "O que Vex esconde?", "Vex"),  # 'Vex' is in the question -> hit
        _q("q3", "Quem é o rei?", "Doran"),  # 'Doran' absent from question -> miss
    ],
)


@pytest.fixture
def world(tmp_path: Path) -> Iterator[WorldState]:
    engine = create_engine(f"sqlite:///{tmp_path / 'h.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as session:
        yield WorldState(session)


def _run(world: WorldState) -> ScenarioResult:
    config = HarnessConfig(name="baseline", use_retrieval=True, use_reflection=False)
    return run_scenario(_MINI, config, FakeLlmClient(), _FakeMem0(), world)


def test_run_scenario_returns_scenario_result(world: WorldState) -> None:
    result = _run(world)

    assert isinstance(result, ScenarioResult)
    assert result.scenario_id == "mini-01"
    assert result.config_name == "baseline"
    assert result.total == 3
    assert result.correct == 2  # q1, q2 hit; q3 miss
    assert result.recall_rate == pytest.approx(2 / 3)
    assert result.total_cost_usd == 0.0  # fake is free
    assert result.avg_cost_usd == 0.0


def test_run_scenario_is_deterministic(world: WorldState) -> None:
    a = _run(world)
    b = _run(world)
    assert (a.correct, a.total, a.recall_rate) == (b.correct, b.total, b.recall_rate)


def test_simple_recall_judge_matches_variants() -> None:
    q = Question(
        id="q",
        asked_after_turn=1,
        category="recall_factual",
        question="Quem descobriu a traição?",
        ground_truth="Aria",
        acceptable_variants=["a cavaleira Aria"],
    )
    assert simple_recall_judge(q, "Foi a cavaleira ARIA quem descobriu.") is True
    assert simple_recall_judge(q, "Foi o conselheiro.") is False
