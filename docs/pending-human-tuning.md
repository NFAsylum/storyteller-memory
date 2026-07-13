# Pendências de tuning humano (Marco)

Itens qualitativos que dependem de rodar o LLM local e julgar a saída — o CLAUDE.md
reserva prompt-tuning pro humano. A **mecânica** está pronta e testada; o que falta é
**calibrar a redação** lendo o output do 7B.

## T1.2 — Prompt de continuação (`core/prompts/story_continuation.txt`)

Estrutura final (placeholders `{genre}/{tone}/{pov}/{target_length}/{content_intensity}`,
regras anti-clichê, 2 few-shot de "concretude"). **Falta:** rodar 2-3 turnos por gênero
com `LLM_BACKEND=local`, ler a prosa e ajustar:
- a redação das regras e dos exemplos few-shot (troque livremente o conteúdo);
- as strings de diretiva em `core/session_config.py` (`_GENRE_DIRECTIVE`, `_TONE_DIRECTIVE`,
  etc.) — **mantenha as chaves**, tune o texto.

Critério (DoD T1.2): mesmo brief em `fantasy` vs `scifi` deve gerar prosa visivelmente
distinta e menos clichê que o baseline. Estimado ~30-60 min iterativo.

Como comparar rápido:
```bash
# criar 2 sessões com genres diferentes e o mesmo primeiro turno, comparar a narração
LLM_BACKEND=local .venv/bin/uvicorn api.main:app --port 8000
# POST /sessions {config:{genre:"fantasy"}} e {genre:"scifi"}, POST .../turn mesmo texto
```

## Reflection cada 2 turnos (T1.1) — observar ruído

`DEFAULT_REFLECT_EVERY=2` popula o inspector cedo, mas o 7B extrai fatos ruidosos com
mais frequência. Se ficar ruim na prática, alternativas: modelo maior só pra reflection
(audit 1.3) ou o edit/delete de fatos (T3.3). Decisão sua depois de ver em uso real.
