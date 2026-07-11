# Experiments — Storyteller

## Sprint 4 (S4.3) — iteração de prompt + retrieval

Backend: `local` (Qwen2.5-Coder-7B local). **Métrica de decisão: `recall_rate`** (containment — determinística e confiável). `consistency_score` e `hallucination_rate` vêm dos judges LLM locais e são **indicativos** (o 7B é ruidoso — ver achado da reflection no Sprint 3).

Método: 4 variantes (2 no eixo prompt, 2 no eixo retrieval) rodadas sobre os 5 cenários `full` (30 perguntas). `qa_base` é a referência compartilhada.

| variant_id | eixo | recall_rate | consistency_score\* | hallucination_rate\* | avg_cost_per_turn |
|---|---|---:|---:|---:|---:|
| `qa_base` | prompt | 63% | 0.67 | 27% | $0.0000 |
| `qa_strict` | prompt | 33% | 0.60 | 23% | $0.0000 |
| `retr_reflection` | retrieval | 33% | 0.90 | 10% | $0.0000 |
| `retr_top2` | retrieval | 17% | 0.65 | 3% | $0.0000 |

\* indicativo (judge LLM local ruidoso), não usado como critério de decisão.

## Decisão

**Vencedor: `qa_base`** — maior `recall_rate` (63%). A decisão é pelo recall porque é a única métrica determinística/confiável aqui; os judges subjetivos rodam no mesmo 7B ruidoso e servem só de sinal. Config salva em `configs/best.yaml`.

## Próximos experimentos sugeridos

- Rodar os judges subjetivos num modelo mais forte (Anthropic) pra calibrar (S4.2).
- Gate na reflection (só injetar fatos estruturados em histórico longo / alta confiança), dado que ela piorou o recall em cenários de 16 turnos.
