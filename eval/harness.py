"""Eval harness v1: run a scenario's turns, ask its questions, score recall + cost.

Components (llm, memory, world_state) are injected so the harness is pure orchestration:
the caller wires real ones for measurement or fakes for a fast, deterministic test.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from core.llm_client import LlmClient
from core.memory.reflection import LlmReflection
from core.memory.retrieval_policy import ContextBundle, RetrievalPolicy
from core.memory.world_state import WorldState
from core.story_loop import StoryLoop
from eval.scenario import Question, Scenario

_QA_SYSTEM = """You answer questions about an ongoing story using ONLY the context below.

<context>
{context}
</context>

Answer in one short sentence based on the context. If the context does not contain the
answer, reply exactly: não sei."""

RecallJudge = Callable[[Question, str], bool]


class _Memory(Protocol):
    session_id: str

    def add(self, text: str, metadata: dict[str, Any] | None = ...) -> str: ...
    def search(self, query: str, top_k: int = ...) -> list[Any]: ...
    def clear(self) -> None: ...


@dataclass(frozen=True)
class HarnessConfig:
    name: str
    use_retrieval: bool = True
    use_reflection: bool = False
    reflect_every: int = 5


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    config_name: str
    correct: int
    total: int
    recall_rate: float
    total_cost_usd: float
    avg_cost_usd: float  # total cost / number of questions


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def simple_recall_judge(question: Question, response_text: str) -> bool:
    """Deterministic recall check: ground_truth or an accepted variant appears in the reply."""
    haystack = _normalize(response_text)
    needles = [question.ground_truth, *question.acceptable_variants]
    return any(_normalize(n) in haystack for n in needles)


def _render_context(bundle: ContextBundle) -> str:
    parts: list[str] = []
    if bundle.active_characters:
        parts.append("Personagens: " + ", ".join(bundle.active_characters))
    if bundle.structured_facts:
        parts.append("Fatos: " + "; ".join(bundle.structured_facts))
    if bundle.raw_memories:
        parts.append("Memórias:\n" + "\n".join(bundle.raw_memories))
    return "\n".join(parts) or "(sem contexto)"


def run_scenario(
    scenario: Scenario,
    config: HarnessConfig,
    llm: LlmClient,
    memory: _Memory,
    world_state: WorldState,
    *,
    recall_judge: RecallJudge = simple_recall_judge,
) -> ScenarioResult:
    session_id = memory.session_id
    memory.clear()

    retrieval = RetrievalPolicy(memory, world_state) if config.use_retrieval else None
    reflection = LlmReflection(llm, world_state, memory) if config.use_reflection else None
    loop = StoryLoop(
        session_id,
        memory=memory,
        llm=llm,
        retrieval_policy=retrieval,
        reflection=reflection,
        reflect_every=config.reflect_every,
    )

    questions_by_turn: dict[int, list[Question]] = defaultdict(list)
    for question in scenario.questions:
        questions_by_turn[question.asked_after_turn].append(question)
    scene_turns = {scene.turn_id for scene in scenario.scenes}

    total_cost = 0.0
    correct = 0

    def ask(question: Question, current_turn: int) -> None:
        nonlocal total_cost, correct
        answer, cost = _answer_question(question, retrieval, llm, session_id, current_turn)
        total_cost += cost
        if recall_judge(question, answer):
            correct += 1

    last_turn = 0
    for scene in sorted(scenario.scenes, key=lambda s: s.turn_id):
        turn_result = loop.run_turn(scene.user_input)
        total_cost += turn_result.cost_usd
        last_turn = scene.turn_id
        for question in questions_by_turn.get(scene.turn_id, []):
            ask(question, scene.turn_id)

    # Questions whose asked_after_turn isn't a scene turn (e.g. > last scene): ask at the end.
    for question in scenario.questions:
        if question.asked_after_turn not in scene_turns:
            ask(question, last_turn)

    total = len(scenario.questions)
    return ScenarioResult(
        scenario_id=scenario.id,
        config_name=config.name,
        correct=correct,
        total=total,
        recall_rate=correct / total if total else 0.0,
        total_cost_usd=total_cost,
        avg_cost_usd=total_cost / total if total else 0.0,
    )


def _answer_question(
    question: Question,
    retrieval: RetrievalPolicy | None,
    llm: LlmClient,
    session_id: str,
    current_turn: int,
) -> tuple[str, float]:
    if retrieval is not None:
        context = _render_context(retrieval.build_context(session_id, current_turn, question.question))
    else:
        context = "(sem contexto)"
    response = llm.generate(
        system=_QA_SYSTEM.format(context=context),
        messages=[{"role": "user", "content": question.question}],
    )
    return response.content, response.cost_usd
