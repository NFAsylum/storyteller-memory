# Session report — Trilha "Produto Usável" (2026-07-13)

Execução da trilha do inbox 2026-07-12 (FASE 1–7, 17 tasks). **Todas as tasks estão
code-complete.** Custo LLM: **$0** (backend local/fake). O que resta é verificação
visual/manual (precisa browser — Marco) e tuning de prosa (Marco).

## Entregue (por fase → PR)

| Fase | Tasks | PRs |
| --- | --- | --- |
| **1** — fixes críticos | T1.1 reflection@turno2 + `/raw-memories`; T1.2 prompt com placeholders (mecânica); T1.3 `/health` estruturado + rate limit + CORS; T1.4 `/turn-streamed` SSE | #5, #6, #7 |
| **2** — controles de intent | T2.1 config genre/pov/tone/length + wizard + chip; T2.2 protagonist + **max_tokens real**; T2.3 story-starters | #7, #9, #10, #19 |
| **3** — memory inspector | T3.1 cards ricos + edit/delete; T3.2 grafo de relações (SVG inline); T3.3 CRUD de fatos falsos | #11, #12, #14 |
| **4** — chat UX | T4.1 edit/regenerate/undo turno; T4.2 timestamps + actor distinto + auto-scroll | #15, #16 |
| **5** — persistência | T5.1 export (md/txt/json); T5.2 fork | #15, #16 |
| **6** — responsivo/tema | T6.1 layout responsivo (drawers); T6.2 theme toggle dark/light | #17, #18 |
| **7** — onboarding | T7.1 hero de 1ª visita + "como funciona" | #17 |

**Decisões documentadas:** Q1 (grafo → SVG inline, não reactflow) em `docs/questions-archive/`.

## Verificação (meu lado)

- **Backend:** `.venv/bin/python -m pytest tests/` → **139 passed**; `ruff` limpo.
- **Frontend:** `cd ui && npm run test` (Vitest) verde; `npm run build` + `tsc --noEmit` limpos.
- **e2e via curl** (health/CORS/create/turn/state/compare) validado.

## Pendente (precisa do Marco)

1. **Mergear PRs abertos:** #17 (tema+onboarding), #18 (responsivo), #19 (max_tokens).
2. **Verificação visual/browser** (não tenho browser no container):
   - Screenshots em `docs/screenshots/` (roteiro em `docs/screenshots/README.md`) + GIF.
   - Playwright viewport tests da T6.1 em 5 tamanhos (`docs/screenshots/responsive/`).
   - QA manual do fluxo completo + dark mode.
   - Screenshot do produto real no README.
3. **Tuning de prosa** (`docs/pending-human-tuning.md`) — rodar o 7B, ler, ajustar a redação do prompt/diretivas.

## Deferrals sinalizados (além do DoD core)

- "Start example story" pré-populado no hero (precisa seed no backend).
- Soft-flag `user_corrected` no mem0 ao deletar fato (a exclusão estruturada já cobre a DoD).
- Filtro por range de valência no grafo (hover + filtro por tipo já entram).

## Rodar

```bash
LLM_BACKEND=local poetry run uvicorn api.main:app --port 8000   # ou =fake, offline
cd ui && npm install && npm run dev                             # http://localhost:3000
```
