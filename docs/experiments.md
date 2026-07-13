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

## F1.6 — Qualidade de output: anti-repetição + trava de idioma (2026-07-13)

Dois sintomas reportados em uso real com o backend `local` (Qwen 7B, `temperature=0`, `seed=42`): (1) repetição esporádica da mesma informação; (2) drift de idioma (resposta inteira em inglês numa história em PT). `temperature=0` sem penalty amplifica ambos — o modelo trava em modos determinísticos (repetição léxica ou switch de idioma) que sampling estocástico normalmente quebraria.

Cinco fixes (ordenados por ROI):

| Fix | Onde | O quê |
|---|---|---|
| T-REP.1 | `core/llm_local.py` | `frequency_penalty=0.3`, `presence_penalty=0.3`, `extra_body.repeat_penalty=1.15` no call. Determinismo preservado (só desviam de token repetido). Não aplicado no Anthropic. |
| T-REP.2 | `core/memory/retrieval_policy.py` | score threshold (default 0.5) no `mem0.search`: memórias fracamente relacionadas viram noise re-narrado. |
| T-REP.3 | `core/memory/retrieval_policy.py` | dedup Jaccard (`_overlap_ratio ≥ 0.6`) entre `raw_memories` e `structured_facts` — o mesmo evento aparecia nos dois canais. |
| T-REP.4 | `core/prompts/story_continuation.txt` | regra "memórias são CONTEXTO, não CONTEÚDO a repetir" + consistency check + exemplo de repetição. |
| T-LANG.1 | `core/prompts/story_continuation.txt` | bloco `<language_lock>` no topo, exemplo de concretude em PT, e reminder de idioma no final (o fim do prompt tem peso desproporcional). |

Cobertura automatizada: `test_llm_local` (params de sampling), `test_retrieval_policy` (score threshold + dedup). Suíte 144 passed.

**Validação qualitativa (antes/depois) — pendente de uso real:** requer rodar sessões de 5+ turnos no backend `local` e comparar (menos repetição/eco; zero drift de idioma em PT; sessão em EN continua em EN). É julgamento humano — o CLAUDE.md reserva tuning de prompt pro humano; se o prompt não convergir em 3 iterações, escalar.

**T-REP.5 (dedup semântica de story_beats na reflection): em STANDBY** por decisão de 2026-07-13 — só acionar se houver repetição *sistemática* (não esporádica) após estes fixes em uso real (gatilho documentado no inbox/audit issue #05).
