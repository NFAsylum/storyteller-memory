# `FakeReflection`/`LlmReflection` não deduplicam `story_beats` em reruns

**Severity:** High
**Priority:** P1
**Category:** Logic
**Source:** `core/memory/reflection.py:100-108` (Fake), `core/memory/reflection.py:425-438` (Llm)

## Descrição

`FakeReflection.consolidate` sempre insere um novo StoryBeat, sem checar se um
beat com mesmo `session_id`, `turn`, `summary` já existe:

```python
self._world.add(
    StoryBeat(
        session_id=session_id,
        summary=f"Consolidated turns {first_turn}-{last_turn}: {len(candidates)} character(s)",
        turn=last_turn,
        importance=min(10, 1 + len(candidates)),
        tags=[],
    )
)
self._world.commit()
```

`LlmReflection._persist_beats` idem — cria N novos beats por chamada, sem dedupe:

```python
def _persist_beats(self, session_id, extraction, last_turn) -> int:
    for beat in extraction.beats:
        self._world.add(StoryBeat(session_id=session_id, summary=beat.summary, ...))
    return len(extraction.beats)
```

Personagens/locations/relations têm dedupe (linha 123, 143-144, 407-410), mas
beats não.

O teste `test_repeated_event_does_not_duplicate` (test_reflection.py:88-98)
verifica que `Aria` não duplica como Character, mas **não checa StoryBeat count**.
Sob o assert, o count de beats depois de 2 reflections seria 2 e o teste passaria.

## Risco

Cenários onde o bug materializa:

1. **`POST /sessions/{id}/reflect` sendo chamado duas vezes** (o Sprint 5 UI tem
   botão "Force reflection now") — cada clique cria beats duplicados a partir de
   turnos que já foram consolidados. `since_turn=0` em `api/main.py:189` significa
   que **toda** a história é reconsolidada a cada clique.

2. **Retry de request HTTP** (browser reenvia) — mesmo com filtragem por
   `since_turn`, `LlmReflection` grava tudo o que o LLM retornou. Se o mesmo
   input passar duas vezes, dois conjuntos de beats aparecem.

3. **`RetrievalPolicy.top_beats` retorna duplicatas**: `retrieval_policy.py:46`
   pega top-K por importância + turn. Se dois beats têm summary idêntico e
   importância igual, os dois vão pro prompt via `structured_facts`. O modelo
   vê a mesma informação duas vezes, tokens são desperdiçados e pode enviesar a
   resposta (repetição = "importante").

4. **Memory Inspector do Sprint 5** mostra story_beats na aba direita — duplicatas
   visíveis quebram a percepção de qualidade do produto.

## Fix sugerido

Opção A — dedup por chave natural em `_persist_beats` (LlmReflection):
```python
def _persist_beats(self, session_id, extraction, last_turn) -> int:
    existing = {(b.turn, b.summary.strip()) for b in self._world.list(StoryBeat, session_id)}
    created = 0
    for beat in extraction.beats:
        key = (beat.turn or last_turn, beat.summary.strip())
        if key in existing:
            continue
        self._world.add(StoryBeat(session_id=session_id, ...))
        existing.add(key)
        created += 1
    return created
```

Opção B — endpoint `POST /reflect` passa `since_turn=session.last_reflection_turn`
em vez de `0`. Requer novo campo `Session.last_reflection_turn: int` (nova
migration) e atualização depois de cada consolidação bem-sucedida.

Opção C (mais simples): index unique parcial `(session_id, turn, summary)` no
Alembic. Quebra bruto qualquer duplicata via constraint. Se rejeição da row
matar a request, tratar `IntegrityError`.

**Recomendação combinada**: A + B. A previne no código; B evita reprocessamento
desnecessário e é natural pro botão "Force reflection now".

Adicionar teste explícito:
```python
def test_reflection_does_not_duplicate_beats_on_rerun(world):
    records = [_turn(1, "Aria."), _turn(2, "Aria."), _turn(3, "Aria.")]
    _reflect(world, records, since_turn=0)
    _reflect(world, records, since_turn=0)
    assert len(world.list(StoryBeat, SESSION)) == 1
```

## Referências

- SQLAlchemy UniqueConstraint: https://docs.sqlalchemy.org/en/20/core/constraints.html
