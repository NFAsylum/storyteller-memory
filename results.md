# Resultados — Storyteller

Backend: `local` (Qwen2.5-Coder-7B via llama-server). Recall julgado por containment (`ground_truth`/variante aparece na resposta), aplicado igual a todos os configs.

## Sprint 3 — recall por config (30 perguntas, 3 cenários seed)

sprint 3 no_memory (LLM puro): 0 of 30 recall (0%)
sprint 3 mem0_only: 27 of 30 recall (90%)
sprint 3 mem0 + reflection: 28 of 30 recall (93%)

Custo total: $0.0000 (backend local)

## Número-manchete

Sem nenhuma memória, o mesmo LLM acerta **0%** das 30 perguntas; com o sistema de memória (mem0), sobe pra **90%** — um salto de **+90pp** que vem inteiramente da infra de memória, não de trocar o modelo.

## Nota metodológica

O delta mem0-only vs mem0+reflection é pequeno (+3pp) porque os cenários seed são curtos (5 turnos): o retrieval top-5 do mem0 já traz as memórias cruas com todos os fatos, saturando o baseline. A reflection (fatos consolidados no world_state) rende mais em históricos longos, onde a memória crua não cabe/fica ruidosa. A diferença que importa pro portfólio é "sem memória" vs "com sistema de memória", não mem0 vs mem0+reflection.

Comparação justa: os 3 configs usam o **mesmo** prompt de QA (que manda responder "não sei" quando o contexto não tem a resposta). No `no_memory` o modelo se abstém em vez de chutar, então o 0% reflete incapacidade genuína sem memória — o único fator que muda entre os configs é a presença (e a forma) da memória.
