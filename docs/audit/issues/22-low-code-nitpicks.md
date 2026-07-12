# Nitpicks de código (consolidado)

**Severity:** Low
**Priority:** P3
**Category:** Code-guidelines
**Source:** Vários (listados abaixo)

## Descrição

Coleção de pontos individuais pequenos demais pra virar issue isolado. Consolidados
aqui pra passar num único sweep.

### N1 — Comentário TL;DR em `world_state.py:5-6` cita módulos futuros
```python
"""... The higher-level domain helpers (record_turn_entities, top_facts,
active_characters) arrive with reflection/retrieval in S2.2/S2.3.
"""
```
Sprint 2 já fechou. `active_characters` existe (linha 119). `record_turn_entities`
e `top_facts` **não existem**. Docstring desatualizada. Removê-los ou trocar
por "provided helpers" com a lista real.

### N2 — Assinatura de `WorldState.__init__` documentada em `architecture.md` diverge do código
`architecture.md:97-98` diz:
```
- `WorldState(session_id, min_last_seen_turn: int)` ... etc.
```
Código real: `def __init__(self, session: Session) -> None:`. Doc drift já
coberto em issue 11 mas re-menciono aqui.

### N3 — `_slot` helper em `story_loop.py:37-38` — nome opaco
```python
def _slot(items: list[str], sep: str) -> str:
    return sep.join(i for i in items if i) or _EMPTY_SLOT
```
Nome `_slot` não explica que retorna string juntada com fallback. Renomear pra
`_join_or_empty(items, sep)`.

### N4 — `_context_dict` no story_loop pode retornar `{}` sem `bundle` na fake path
```python
def _context_dict(self, bundle: ContextBundle | None) -> dict[str, Any]:
    if bundle is None:
        return {"raw_memories": [], "active_characters": [], "turn": self._turn}
    return {**bundle.model_dump(), "turn": self._turn}
```
Sem bundle não retorna `structured_facts` nem `token_estimate`. Chamador (API,
UI) pode esperar chaves consistentes. Adicionar defaults na branch None:
```python
return {"raw_memories": [], "structured_facts": [], "active_characters": [],
        "token_estimate": 0, "turn": self._turn}
```

### N5 — `docstring` do `active_characters` menciona "most-recently-seen first" mas ordem também tem tie-break por `id`
```python
def active_characters(self, session_id: str, min_last_seen_turn: int) -> list[Character]:
    """Characters seen at or after a turn threshold (most-recently-seen first)."""
    stmt = (
        select(Character)
        .where(...)
        .order_by(Character.last_seen_turn.desc(), Character.id)  # tie-break por id
    )
```
Docstring podia dizer "..., tie-break by insertion order (id ascending)".

### N6 — `_reset_world` duplicado em `run_all_scenarios.py:56-59` e `run_experiments.py:63-66`
Mesmo bloco de código em 2 arquivos:
```python
def _reset_world(session, session_id: str) -> None:
    for model in (StoryBeat, Relation, Location, Character):
        session.execute(delete(model).where(model.session_id == session_id))
    session.commit()
```
Mover pra `eval/harness.py` (público) e importar.

### N7 — `LlmResponse.usage` type `dict[str, int]` mas nada valida chaves
```python
class LlmResponse(BaseModel):
    ...
    usage: dict[str, int]
```
Callers assumem `usage["input_tokens"]` e `usage["output_tokens"]`. Um backend
que retorne `{"prompt_tokens": ..., "completion_tokens": ...}` (OpenAI-ish) e
esqueça de traduzir vai crashar em runtime. Melhor tornar Pydantic model:
```python
class LlmUsage(BaseModel):
    input_tokens: int
    output_tokens: int

class LlmResponse(BaseModel):
    ...
    usage: LlmUsage
```

### N8 — `create_llm_client("gpt")` (test) espera ValueError, mas erro message diz "expected 'fake', 'anthropic', or 'local'"
Test em `test_llm_client.py:129-131`:
```python
def test_factory_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError):
        create_llm_client("gpt")
```
Melhor asserção específica: `pytest.raises(ValueError, match="expected 'fake'")`.

### N9 — `f"{scenario.id}--{config_name}"` (run_all_scenarios.py:75) usa `--` como separador
Se um `scenario.id` contiver "--" no futuro, parse ambíguo. Nada quebra hoje.
Usar caractere que não pode aparecer em IDs (ex: `\x00` — ok em Python strings,
proibido em nomes).

### N10 — `# noqa: BLE001` em smoke_local.py:33
```python
except Exception as exc:  # noqa: BLE001 - smoke script, surface any failure
```
Comentário justifica; OK. Só nota que existe.

### N11 — `logger.info(...)` em anthropic client mas `.propagate` não configurado
Sem `logging.basicConfig()` na app entry (nem CLI, nem API), os logs `info` do
`llm_anthropic` **nunca aparecem** — root logger default é WARNING. Adicionar
setup mínimo em `api/main.py`:
```python
import logging
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
```

### N12 — `LOG_LEVEL=INFO` está no `.env` mas nada lê essa var
Grep confirmou: `LOG_LEVEL` só aparece em `.env` e `.env.example`, nunca no
código. Configurar (ver N11) ou remover do `.env.example` como config morta.

## Risco

Cada item individualmente: negligível. Cumulativamente: sensação de "código
inacabado" no code review externo. Corrigir num só sweep = 1-2h de trabalho.

## Fix sugerido

Passe único de "chore/polish":
1. N1, N5 — docstrings
2. N3 — rename `_slot`
3. N4, N7 — schemas mais estritos
4. N6 — dedup helper
5. N8, N11, N12 — polish
6. N2 — coberto por issue 11 (doc)
7. N9, N10 — reconhecer, não mexer

Marcar como "sprint hygiene" no `docs/tasks.md` Sprint 6 (bugfixes/polish
já reservado 4h ali).
