# `judge_consistency` recebe `{traits: [ground_truth], backstory: question}` — não mede consistência real

**Severity:** Medium
**Priority:** P2
**Category:** Eval
**Source:** `eval/run_experiments.py:93-99`, `eval/judges.py:81-97`

## Descrição

O harness de experiments do S4.3 monta um "character profile" pra alimentar o
`judge_consistency`:

```python
consistency = [
    judge.judge_consistency(
        {"name": "", "traits": [q.ground_truth], "relations": [], "backstory": q.question}, a
    )
    for q, a in answers
    if q.category.value == "character_consistency"
]
```

O que essa estrutura significa:
- `name=""` — perfil sem nome.
- `traits=[ground_truth]` — o traço "esperado" da resposta correta vira único
  trait do personagem.
- `relations=[]` — sem contexto de relacionamentos.
- `backstory=question` — a pergunta vira o "backstory".

O prompt em `eval/prompts/judge_consistency.txt` diz:
> Rate how well the response respects the established character profile ...

Mas o "profile" acima não é o perfil de personagem — é uma coleção artificial de
strings do dataset. O juiz LLM avalia se a resposta menciona `ground_truth` num
contexto que se parece com a `question`. É uma métrica frankenstein.

Reconhecido em code review interno: o comentário do S4.3
(`docs/tasks.md:206-209`) afirma que a calibração real está adiada:
> **Parcial (decisão C, 2026-07-11)**: `judge_consistency` implementado + testado
> (mock). A **calibração** ... fica **adiada** até Marco fornecer os scores
> humanos de referência.

E `eval/run_experiments.py:120-124` marca a métrica como "indicativa":
> `consistency_score` e `hallucination_rate` vêm dos judges LLM locais e são
> **indicativos** (o 7B é ruidoso — ver achado da reflection no Sprint 3).

## Risco

- **Métrica reportada em `docs/experiments.md`** tem uma coluna que não mede o
  que promete. Leitor externo do portfólio pode acreditar que essa é uma métrica
  de consistência de personagem real.
- **Fundamento do winner selection**: `run_experiments.py:180` decide vencedor
  por `recall_rate` (bom — coluna determinística). Mas `consistency_score` e
  `hallucination_rate` aparecem na tabela ao lado do vencedor, sugerindo autoridade
  que não têm.
- **Deferido pra S4.2**: já está no radar (task pending), mas a métrica atual
  ainda é reportada. Contradição.

## Fix sugerido

Curto prazo (antes de commit de `docs/experiments.md` gerado):

1. **Marcar coluna `consistency_score` explicitamente como `n/a — não calibrada`**
   em `_write_experiments_md`. Aparece na tabela mas sem valor numérico enganoso.

2. **Não passar `q.ground_truth` como trait** — passar `{"traits": []}` explícito
   e fazer o juiz reportar "sem perfil, não posso avaliar" (o juiz LLM
   provavelmente vai devolver 0.5 default, o que já é um sinal claro).

3. **Bloquear cálculo até S4.2 concluído**:
   ```python
   if not CONSISTENCY_CALIBRATED:
       consistency = []  # não reporta
   ```
   E logar warning: "Consistency judge not calibrated; skipping."

Médio prazo (S4.2 real):

4. **Extrair perfil de personagem do próprio scenario JSON**. Estender
   `Question`/`Scenario` schema:
   ```json
   {
     "characters": {
       "Vex": {
         "traits": ["frio", "ambicioso"],
         "relations": [{"with": "Aria", "kind": "traição"}],
         "backstory": "conselheiro traidor do reino"
       }
     }
   }
   ```
   E a pergunta `character_consistency` referencia `"about_character": "Vex"`.
   Aí `judge_consistency` recebe um perfil real, não um proxy.

5. Passar juiz por Anthropic (S4.2 gate 80% agreement) — o 7B local é ruidoso
   demais pra pontuar diferença fina de consistência.

## Referências

- Escreveu explicitamente em `docs/tasks.md:206-209` como decisão C (parcial).
- Rubric-based LLM-as-judge: https://arxiv.org/abs/2306.05685 (Chatbot Arena)
