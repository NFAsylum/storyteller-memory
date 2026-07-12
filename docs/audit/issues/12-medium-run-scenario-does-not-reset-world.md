# `run_scenario` limpa mem0 mas não `world_state` — contaminação entre runs no mesmo processo

**Severity:** Medium
**Priority:** P2
**Category:** Eval / Logic
**Source:** `eval/harness.py:120-131`, `eval/run_all_scenarios.py:56-88`

## Descrição

`run_scenario` limpa apenas a memória vetorial:

```python
def run_scenario(
    scenario: Scenario, config: HarnessConfig, llm, memory, world_state,
    *,
    recall_judge=simple_recall_judge, qa_system=_QA_SYSTEM,
) -> ScenarioResult:
    session_id = memory.session_id
    memory.clear()  # <-- apenas mem0
    # world_state NÃO é limpo aqui
    ...
```

A limpeza do world_state (characters/locations/relations/story_beats) só acontece
nos wrappers externos, `run_all_scenarios.py:56-59` e `run_experiments.py:63-66`:

```python
def _reset_world(session, session_id: str) -> None:
    for model in (StoryBeat, Relation, Location, Character):
        session.execute(delete(model).where(model.session_id == session_id))
    session.commit()
```

Quem chama `run_scenario` diretamente (tests + eventuais scripts futuros) sem
antes chamar `_reset_world` reusa estado de runs anteriores.

## Risco

1. **Testes**: `tests/test_harness.py:83-85` roda o mini scenario com `world`
   sendo uma fixture per-test (SQLite temporário) — não afeta. Mas se um dia
   virar fixture module-scoped ou session-scoped pra economizar tempo, testes
   passam a ser dependentes de ordem.

2. **Scripts ad-hoc**: qualquer script novo que faça
   ```python
   for config in configs:
       run_scenario(scenario, config, llm, memory, world)
   ```
   sem `_reset_world` entre iterações vai medir "config B" com o world_state
   deixado pela "config A". Métrica corrompida silenciosamente.

3. **Sprint 4 experiments** (`run_experiments.py`) — parte OK porque cada variante
   usa `session_id = f"{scenario.id}--{variant.variant_id}"` (linha 76) e
   `_reset_world(session, session_id)` roda antes. Mas o *contrato* de
   `run_scenario` fica frágil: alguém que reusa `session_id` sofre.

4. **Reflection stateful**: como reflection popula `story_beats` que depois viram
   `structured_facts` no context bundle, contaminação afeta diretamente o output
   do LLM. Diferença entre "config C rodada primeiro" e "config C rodada por
   último" pode ser mensurável.

## Fix sugerido

Opção A — `run_scenario` limpa tudo consistentemente:
```python
def run_scenario(scenario, config, llm, memory, world_state, ...):
    session_id = memory.session_id
    memory.clear()
    _reset_world_state(world_state._session, session_id)  # <-- add
    ...
```

Precisa expor `_reset_world` como helper público ou passar `session_factory` — a
API fica mais complexa.

Opção B — documentar o contrato claramente:
```python
def run_scenario(scenario, config, llm, memory, world_state, ...):
    """Run a scenario end-to-end.

    Preconditions:
      - memory.clear() will be called; caller does NOT need to pre-clear.
      - world_state is assumed to be fresh for this session_id. Caller MUST
        delete characters/locations/relations/story_beats for the session_id
        before invoking. See eval/run_all_scenarios.py::_reset_world for helper.
    """
```

Opção C — mover `_reset_world` pra `eval/harness.py` como parte do contrato de
run e chamá-lo internamente. Requer refactor da assinatura pra receber `session`
(não só WorldState).

**Recomendação**: A. Padrão do "cliente chama, callee limpa" é mais robusto e
os wrappers atuais já fazem isso. Preserva as chamadas existentes (idempotente).

## Referências

- Test hermeticity: cada teste tem que rodar independente da ordem —
  https://testing.googleblog.com/2008/08/by-miko-hevery-so-you-decided-to.html
