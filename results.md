# Resultados — Storyteller

Backend: `local` (Qwen2.5-Coder-7B via llama-server). Recall julgado por containment (`ground_truth`/variante aparece na resposta), igual pra todos os configs.

## Cenários curtos (5 turnos) — recall (30 perguntas, 3 cenários)

- no_memory (LLM puro): 0 of 30 recall (0%)
- mem0_only: 27 of 30 recall (90%)
- mem0 + reflection: 28 of 30 recall (93%)

## Cenários estendidos (16 turnos) — recall (30 perguntas, 3 cenários)

- no_memory (LLM puro): 0 of 30 recall (0%)
- mem0_only: 24 of 30 recall (80%)
- mem0 + reflection: 20 of 30 recall (67%)

Custo total: $0.0000 (backend local)

## Número-manchete

Sem nenhuma memória, o mesmo LLM acerta **0%** das 30 perguntas; com o sistema de memória (mem0), sobe pra **90%** — um salto de **+90pp** que vem inteiramente da infra de memória, não de trocar o modelo.

## Nota metodológica — reflection vs mem0 cru

Delta mem0-only → mem0+reflection: curtos **+3pp**, estendidos **-13pp**.

**Achado (negativo, mas honesto):** nos cenários longos a reflection **piorou** o recall. O mem0 recupera por similaridade e já traz as memórias cruas (limpas e corretas) relevantes; a reflection injeta fatos estruturados gerados pelo Qwen 7B local, que são ruidosos/imprecisos e mais longos — pro modelo pequeno isso distrai em vez de ajudar. Para a reflection compensar seria preciso (a) um modelo mais forte fazendo a consolidação, ou (b) perguntas de síntese pura onde a memória crua não basta. Sprint 4 avalia isso com as 5 categorias + judges subjetivos.

Comparação justa: os 3 configs usam o **mesmo** prompt de QA (que manda responder "não sei" quando o contexto não tem a resposta). No `no_memory` o modelo se abstém em vez de chutar, então o 0% reflete incapacidade genuína — o único fator que muda entre os configs é a presença (e a forma) da memória.
