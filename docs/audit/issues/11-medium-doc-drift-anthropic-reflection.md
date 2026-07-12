# `docs/architecture.md` diz `AnthropicReflection`; código tem `LlmReflection`

**Severity:** Medium
**Priority:** P2
**Category:** Code-guidelines / Design
**Source:** `docs/architecture.md:70`, `docs/architecture.md:100-107`, `core/memory/reflection.py:261`

## Descrição

`docs/architecture.md:70`:
> Mesma lógica pra `Reflection`: `Reflection` Protocol + `FakeReflection` (regra
> determinística) + `AnthropicReflection` (Sprint 3, LLM sumariza).

Mas o código real (`core/memory/reflection.py:261`) declara:
```python
class LlmReflection:
    """Real reflection: the configured LLM (local or Anthropic) summarizes turns to JSON."""
```

E `docs/tasks.md:148` sabe da discrepância mas nunca fez o backport:
> Impl como `LlmReflection` (genérica, recebe `LlmClient`) em vez de
> `AnthropicReflection` — roda com o backend configurado (local, per inbox).

Grep confirma: `AnthropicReflection` aparece apenas em `docs/architecture.md` e
`docs/tasks.md`; **nunca no código**.

## Risco

- Onboarding humano (você lendo o repo em 3 meses, ou revisor externo): leitura
  do `architecture.md` sugere um nome que não existe. `grep AnthropicReflection`
  no source retorna zero. Confusão imediata.
- Portfólio review: reviewer que confia no doc perde tempo procurando classe
  fantasma. Percepção: "docs desatualizadas".
- Copiar/colar snippet do doc quebra o import.

## Fix sugerido

Atualizar `docs/architecture.md` em 2 lugares:

1. Linha 70 — trocar `AnthropicReflection` por `LlmReflection`:
   ```markdown
   Mesma lógica pra `Reflection`: `Reflection` Protocol + `FakeReflection` (regra
   determinística) + `LlmReflection` (Sprint 3, roda com qualquer LlmClient —
   local, Anthropic, ou fake).
   ```

2. Linhas 100-107 — trocar exemplo de assinatura:
   ```markdown
   - `Reflection` Protocol: `consolidate(session_id, since_turn) -> ReflectionResult`
   - `LlmReflection(llm: LlmClient, world_state, memory, *, max_retries=2)`
   - `FakeReflection(world_state, memory)` — regra mecânica keyless
   ```

Também vale um sweep rápido de outras deltas doc→código:

- `docs/architecture.md:48-58` mostra `LlmResponse` com `usage: dict` genérico;
  código tem `usage: dict[str, int]`. OK, mas alinhar não custa.
- `docs/architecture.md:75` menciona `StoryLoop(session_id, memory, world_state, llm)`
  — código real (`story_loop.py:61-72`) é `StoryLoop(session_id, memory, llm, *,
  retrieval_policy=None, reflection=None, reflect_every=5, prompt_template=None,
  start_turn=0)`. **A assinatura mudou; não tem `world_state`.**
- `docs/architecture.md:118` promete `location NER simples (regex por nome próprio
  inicial)` para o retrieval_policy — o código (`retrieval_policy.py`) **não faz
  isso**; NER de locations foi deferido (comment em `story_loop.py:51`:
  "location NER not wired yet").

Sugestão consolidada: escrever novo `docs/architecture.md` após auditoria do
código real. Como esse ficha de 22 lá é out-of-scope, este issue foca só nos 2
matches específicos de `AnthropicReflection`.

## Referências

- CLAUDE.md convenção: "Nunca marcar feita se DoD não é 100% verificável" —
  documentação drift viola o espírito da convenção.
