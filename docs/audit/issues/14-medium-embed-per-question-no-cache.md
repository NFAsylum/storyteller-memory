# Embed rodado a cada pergunta no harness sem cache

**Severity:** Medium
**Priority:** P2
**Category:** Performance
**Source:** `eval/harness.py:157-171`, `eval/harness.py:192-208`, `core/memory/mem0_adapter.py:119-120`

## Descrição

Para cada pergunta do harness, `_answer_question` chama:
```python
if retrieval is not None:
    context = _render_context(retrieval.build_context(session_id, current_turn, question.question))
```

`build_context` chama `memory.search(user_input, top_k=...)` que roda
`Mem0Memory.search(query, user_id=..., limit=...)`. mem0 (via sentence-transformers)
embed a query fresh a cada chamada — nenhum cache.

Custos:
- Embed do `all-MiniLM-L6-v2` em CPU: ~10-30ms por query (dependendo do hardware).
- Full run do S4.3: 4 variantes × 5 cenários × 6 perguntas = 120 embeds só para
  responder perguntas + turnos in-between (~15 turnos por scenario × 5 scenarios
  × 4 variants = 300 embeds para retrieval durante turns). Total ~420 embeds.
- Extra: reflection prompts também podem embutir busca. Não confirmei.

420 × 20ms = 8.4s de embed puro por run de experimento. Pequeno absolutamente,
grande relativo (o LLM local roda em ~5-10s por turno; embed adiciona 4-8%).

**Contexto do achado**: reruns dos mesmos scenarios (frequente durante Sprint 4
iteração) reembedam as mesmíssimas queries. Cache hit rate seria muito alto.

## Risco

- Ciclo lento de iteração no Sprint 4 (custo cumulativo ao longo do desenvolvimento).
- Se migrar pro Anthropic (Sprint 6), embed local não é o gargalo (embed é rápido
  em CPU comparado a network). Mas se um dia trocar embed pra provider remoto
  (OpenAI embeddings, Cohere), custo em $$ vira o problema.
- Se algum dia o harness for expandido (30 → 200 perguntas), o overhead cresce
  linearmente.

Este é o cenário de "não urgente hoje, gargalo amanhã".

## Fix sugerido

Adicionar cache LRU simples em `Mem0Adapter.search`:

```python
from functools import lru_cache

class Mem0Adapter:
    def __init__(self, session_id, memory=None, *, cache_size: int = 128, ...):
        ...
        self._cache_size = cache_size
        # per-instance cache — invalidated by clear()
        self._search_cache: dict[tuple[str, int], list[MemoryRecord]] = {}

    def search(self, query: str, top_k: int = 5) -> list[MemoryRecord]:
        key = (query, top_k)
        if key in self._search_cache:
            return self._search_cache[key]
        result = self._to_records(self._memory.search(query, user_id=self.session_id, limit=top_k))
        # LRU-ish: cap size, drop oldest
        if len(self._search_cache) >= self._cache_size:
            self._search_cache.pop(next(iter(self._search_cache)))
        self._search_cache[key] = result
        return result

    def clear(self) -> None:
        self._search_cache.clear()
        self._memory.delete_all(user_id=self.session_id)

    def add(self, text, metadata=None):
        # invalida cache já que o índice mudou
        self._search_cache.clear()
        ...
```

Alternativa mais elegante: cache no `RetrievalPolicy` scoped por turn, invalidado
quando `current_turn` avança.

Adicionar micro-benchmark opcional:
```python
def test_search_hits_cache_on_repeated_query():
    adapter = Mem0Adapter("s", memory=_mem_with_counting_search())
    adapter.search("Aria")
    adapter.search("Aria")
    assert adapter._underlying_search_calls == 1
```

## Referências

- sentence-transformers docs: https://www.sbert.net/docs/quickstart.html
- functools.lru_cache: https://docs.python.org/3/library/functools.html#functools.lru_cache
