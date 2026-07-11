# Resultados — Storyteller

Backend: `local` (Qwen2.5-Coder-7B via llama-server). Recall julgado por containment (`ground_truth`/variante aparece na resposta), igual pra todos os configs.

## Cenários curtos (5 turnos) — recall (30 perguntas, 3 cenários)

- no_memory (LLM puro): 0 of 30 recall (0%)
- mem0_only: 27 of 30 recall (90%)
- mem0 + reflection: 28 of 30 recall (93%)

Custo total: $0.0000 (backend local)

## Número-manchete

Sem nenhuma memória, o mesmo LLM acerta **0%** das 30 perguntas; com o sistema de memória (mem0), sobe pra **90%** — um salto de **+90pp** que vem inteiramente da infra de memória, não de trocar o modelo.

## Nota metodológica — reflection vs mem0 cru

Delta mem0-only → mem0+reflection nos cenários curtos: **+3pp**.

Comparação justa: os 3 configs usam o **mesmo** prompt de QA (que manda responder "não sei" quando o contexto não tem a resposta). No `no_memory` o modelo se abstém em vez de chutar, então o 0% reflete incapacidade genuína — o único fator que muda entre os configs é a presença (e a forma) da memória.
