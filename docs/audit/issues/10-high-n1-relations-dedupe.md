# `LlmReflection._persist_relations` roda `world.list(Relation, ...)` dentro do loop (N+1 queries)

**Severity:** High
**Priority:** P1
**Category:** Performance
**Source:** `core/memory/reflection.py:398-423`

## Descrição

```python
def _persist_relations(self, session_id, extraction, last_turn) -> int:
    by_name = {c.name: c for c in self._world.list(Character, session_id)}
    created = 0
    for rel in extraction.relations:
        a, b = by_name.get(rel.a), by_name.get(rel.b)
        if a is None or b is None:
            continue
        if any(
            {r.a_character_id, r.b_character_id} == {a.id, b.id} and r.kind == rel.kind
            for r in self._world.list(Relation, session_id)  # <-- query dentro do loop
        ):
            continue
        self._world.add(Relation(...))
        created += 1
    return created
```

`self._world.list(Relation, session_id)` roda `SELECT * FROM relations WHERE
session_id = ?` a cada iteração. Se `extraction.relations` tem N entries, faz
N queries idênticas (sob condições de "nenhuma nova foi criada"; se cria, N
queries retornam listas cada vez maiores).

Mesmo padrão em `FakeReflection._link_top_characters` chama
`self._relation_exists()` que também faz `self._world.list(Relation, session_id)`.
Fake só cria 1 relação por consolidação então impacto é menor, mas o smell é o
mesmo.

## Risco

Escala do impacto:

- 1 reflection sobre 10 turnos com Qwen extraindo 5 relações → 5 SELECT redundantes.
  Baixo em dev, mas...
- 30 questions × 5 scenarios no eval → cada scenario tem 1-2 reflections → dezenas
  de queries desnecessárias em SQLite. SQLite lida OK (µs por query), mas em
  Postgres remoto (Sprint 6) cada round-trip vira 10-50ms.
- Sprint 5 UI com "Force reflection now" numa sessão longa (30+ turnos) — o LLM
  pode extrair 20+ relações. Isso é 400+ ms extra desnecessário.

Impacto adicional: cada `world.list()` retorna todas as relações ordenadas por id,
não usa índice de sessão pra filtro de kind/pair. O trabalho é O(R²) onde R é
número de relações da sessão.

## Fix sugerido

Materializar o set uma vez:

```python
def _persist_relations(self, session_id, extraction, last_turn) -> int:
    by_name = {c.name: c for c in self._world.list(Character, session_id)}
    existing_pairs = {
        (frozenset({r.a_character_id, r.b_character_id}), r.kind)
        for r in self._world.list(Relation, session_id)
    }
    created = 0
    for rel in extraction.relations:
        a, b = by_name.get(rel.a), by_name.get(rel.b)
        if a is None or b is None:
            continue
        key = (frozenset({a.id, b.id}), rel.kind)
        if key in existing_pairs:
            continue
        self._world.add(Relation(...))
        existing_pairs.add(key)
        created += 1
    return created
```

O mesmo pattern (materializar antes do loop) já é usado em `_persist_characters`
(linha 356: `existing = {c.name: c for c in self._world.list(...)}`) — a fix é
apenas replicar essa ideia consistentemente.

Adicionar teste que garante:
```python
def test_llm_reflection_relations_dedupe_uses_single_query(world, monkeypatch):
    call_count = 0
    original = WorldState.list
    def counting_list(self, model, session_id):
        nonlocal call_count
        if model is Relation:
            call_count += 1
        return original(self, model, session_id)
    monkeypatch.setattr(WorldState, "list", counting_list)
    # extraction with 5 relations
    ...
    assert call_count <= 2  # once for dedupe, once for final report
```

## Referências

- Django docs — "The N+1 problem": https://docs.djangoproject.com/en/5.0/topics/db/optimization/
