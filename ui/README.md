# Storyteller — Web UI

Next.js frontend for the Storyteller backend: an interactive storyteller whose
**long-term memory is made visible and falsifiable**. The UI's job is to let you
*feel* the memory working — not just read a recall number in a table.

Built from scratch on the project stack (no code copied from sibling projects):
**Next.js 16 (App Router) · Tailwind CSS 4 · shadcn/ui (Base UI primitives) ·
SWR · Vitest**.

## What it shows

Three columns:

| Column | Component | Purpose |
| --- | --- | --- |
| Left | `SessionsSidebar` | List of stories (SQLite sessions), active one highlighted, "New session" dialog. |
| Center | `ChatArea` | Turn-by-turn narrative (`you → narrator`), free-text input, "Continuing the story…" loader, error toasts (no crash on LLM timeout). |
| Right | `MemoryInspector` | Four tabs with live counts — **Characters / Locations / Relations / Story beats** — populated from the world state as reflection runs. |

### Debug panel (the demo)

- **Compare with/without memory** — the killer feature. Re-runs the last turn twice
  (`no_memory` vs `mem0_only`) and shows both narrations side by side. This is the
  screenshot that proves the point: same prompt, generic answer without memory,
  contextualized answer with it.
- **Force reflection** — triggers `POST /reflect`; toast reports characters/beats updated (or a JSON-failure warning).
- **Last-turn context** — shows the retrieved context bundle (raw memories, structured facts, active characters) that fed the last turn.
- **Clear session** — destructive, with confirmation; deletes the session, its mem0 vectors and world state.

Session id is persisted in a 30-day cookie: reopen the browser and you land back
in the same story, memory intact.

## Running it

The UI needs the Python backend running (it reuses `story_loop`, `mem0`, `world_state`).

```bash
# 1. Backend (repo root) — LLM_BACKEND=local uses the llama-server; =fake is deterministic/offline
cd ..
LLM_BACKEND=local poetry run uvicorn api.main:app --port 8000
#    First request takes ~72s: sentence-transformers/torch import (one-time per process).

# 2. Frontend (this dir)
npm install
npm run dev            # http://localhost:3000
```

The API base URL defaults to `http://localhost:8000` and is overridable with
`NEXT_PUBLIC_API_URL`. CORS on the backend allows `http://localhost:3000` by
default (configurable via `CORS_ORIGINS`).

## Testing

```bash
npm run test          # Vitest — 9 tests across the 4 main components
npm run build         # production build + typecheck
```

Each main component is tested on three axes: render, primary interaction, and
error/loading. jsdom lacks a few DOM APIs Base UI touches — see
`vitest.setup.ts` for the polyfills.

## Screenshots

See [`../docs/screenshots/`](../docs/screenshots/) — chat with memory, the
memory inspector populated, and the with/without-memory split-screen; plus
[`../docs/demo.gif`](../docs/demo.gif) for the end-to-end flow.

## Layout

```
src/
├── app/
│   ├── page.tsx                 # home: session list; resumes cookie session
│   └── sessions/[id]/page.tsx   # story workspace (await params — Next 16)
├── components/
│   ├── workspace.tsx            # 3-column shell
│   ├── sessions-sidebar.tsx · chat-area.tsx · memory-inspector.tsx
│   ├── compare-turn-modal.tsx   # split-screen demo
│   ├── debug-panel.tsx · new-session-dialog.tsx
│   └── *.test.tsx               # Vitest, colocated
└── lib/
    ├── api.ts                   # typed client for the 9 FastAPI endpoints
    ├── hooks.ts                 # SWR hooks (sessions / session / memory state)
    └── session-cookie.ts        # 30-day cookie persistence
```
