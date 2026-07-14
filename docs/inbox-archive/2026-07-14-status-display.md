# INBOX — 2026-07-14 (Storyteller — Model status display)

Após executar, mova pra `docs/inbox-archive/2026-07-14-status-display.md`.

## Status

- 🆕 **T-STATUS.1** — chip visual mostrando backend + modelo em uso

## Contexto

Marco quer signal de "product-grade" nos dois projetos portfolio (Storyteller + Balance). Hoje: `/health` do Storyteller já mostra `backend_llm` mas apenas via curl — não aparece na UI. Balance nem `/health` tem.

**Decisão de 2026-07-14**: implementar **Option A do comparativo** (status display only, sem UI de troca). Zero UX de switching agora — só transparência de "estou usando modelo X via backend Y". Complexidade baixa, signal alto.

## Red lines

- ❌ **`git rebase` proibido.** Use merge.
- ❌ **Sem force push, sem history rewrite.**
- ❌ **Não postar review/comentário/PR no GitHub sem confirmação humana.**
- ❌ **Não mexer em `docker/.env`.**

## T-STATUS.1 [3-4h] — Backend + modelo display

### Contexto técnico específico

**Como Storyteller escolhe modelo hoje** (verificado em `core/llm_local.py:44`):
```python
self.model = model or os.environ.get("LOCAL_LLM_MODEL") or DEFAULT_MODEL
```

**MAS**: llama.cpp/llama-server é permissivo — se você pedir modelo X mas ele só tem Y carregado, ele serve Y sem erro. Env config é *hint*, não verdade. Pra status **real**, precisa consultar `GET http://192.168.3.92:8080/v1/models` e mostrar o que llama-server tem ativo.

### Escopo

**Backend**:

1. Adicionar função `_query_local_model()` em `core/llm_local.py` (ou lugar equivalente) que:
   - Faz `GET {LOCAL_LLM_URL}/v1/models` com timeout curto (2s)
   - Retorna primeiro model id da lista (ou None se falha)
   - Cachear resultado por 30s (evita chamada por request)

2. Enriquecer o endpoint `/health` (em `api/main.py`) — hoje retorna:
   ```json
   {"status":"ok","backend_llm":"local","mem0_ready":true,"db_ready":true}
   ```
   Adicionar campo `llm_model` (o real detectado, não o env):
   ```json
   {"status":"ok","backend_llm":"local","llm_model":"qwen2.5-coder-7b",
    "mem0_ready":true,"db_ready":true}
   ```
   Se backend é `fake`, `llm_model` = `"fake"`. Se `local` mas llama-server offline, `llm_model` = `"local-unreachable"`. Se `anthropic`, `llm_model` = env `ANTHROPIC_MODEL` ou `"claude-sonnet-4-6"`.

**Frontend**:

3. Component novo `<ModelStatusChip />` (em `ui/src/components/model-status-chip.tsx`):
   - Query `/health` via react-query (cache 30s)
   - Renderiza chip pequeno: `[backend · model]` — ex: `[local · qwen2.5-coder-7b]`
   - Cor por backend: local = amber, anthropic = green, fake = gray
   - Tooltip on hover: "Backend LLM: local · Model: qwen2.5-coder-7b · Para trocar: edite .env e reinicie"
   - Loading state: `[carregando…]`
   - Error state: `[backend offline]`

4. Wire no `<Workspace />` header (`ui/src/components/workspace.tsx`), lado direito do header — visível em qualquer sessão.

### DoD

- Backend `/health` retorna `llm_model` corretamente detectado (com env `LLM_BACKEND=local` → mostra o real do llama-server; com `fake` → mostra "fake")
- Cache 30s implementado (chama llama-server no máximo 1x por 30s)
- Timeout de 2s previne backend hang se llama-server unreachable — `llm_model` cai pra `"local-unreachable"` graciosamente
- Chip aparece no header workspace em qualquer sessão
- Chip mostra info correta observada no `/health`
- `pytest tests/` inteiro verde
- `pytest tests/test_api.py::test_health` atualizado pra incluir asserção sobre `llm_model` field
- Vitest tests do `ModelStatusChip` cobrindo: loading, success (com dado), error (backend offline)

### Verificação manual

- Backend em `LLM_BACKEND=local` + llama-server ativo → chip mostra `[local · qwen2.5-coder-7b]`
- Backend em `LLM_BACKEND=local` + llama-server offline → chip mostra `[local · local-unreachable]` (amber)
- Backend em `LLM_BACKEND=fake` → chip mostra `[fake · fake]` (gray)
- Chip persiste ao trocar de sessão

### Se travar

- Se o cache dá race condition estranho: use `functools.lru_cache` com `maxsize=1` + timer manual. Não overengineer.
- Se llama-server responde formato inesperado (não OpenAI-compat): grava o raw response no log e retorna `"local-unknown-format"`. Não abort.

## Diretiva sobre escopo

Executar T-STATUS.1 sozinho. Não mexer em:
- Model switching UI (Option B — fora de escopo, virá depois se demand real)
- `SessionConfig` schema (não adicionar `llm_model` field per-session agora)
- Env config UX (nada de página de settings)

Se qualquer coisa parecer que precisa expandir escopo: **escale**.

## Depois de tudo verde

1. `git push` da branch `dev-marco-status-display`
2. Abrir PR: `feat: model status display (T-STATUS.1)`
3. Body: menciona Option A do comparativo backend/model, escreve trade-off "hint vs verdade" (env vs llama-server actual), inclui screenshot do chip em cada estado
4. **Aguardar autorização humana** pra merge

Reporte no próximo prompt:
- SHA do commit
- Screenshot do chip em cada estado (local ok, local unreachable, fake)
- Confirmação de DoD verde

## Nota sobre estado atual do backend

O processo uvicorn rodando (PID 17033) foi startado com o launcher gambiarra pré-lifespan (T-INFRA.1). PR #23 mergeou o lifespan handler, mas o processo ativo ainda usa a gambiarra. **Antes de rodar seus testes finais**: reinicie o backend com o comando canônico:

```bash
docker exec claude-code-vae bash -c 'pgrep -af "uvicorn api" | grep -v pgrep | awk "{print \$1}" | xargs -r kill'
sleep 3
docker exec -d claude-code-vae bash -c 'cd /workspace && export $(grep -v "^#" .env | xargs) && CORS_ORIGINS=http://localhost:3001 .venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1'
```

Verifique que `/health` retorna 200 sem sentar 500 primeiro (evidência de que lifespan funcionou). Se falhar, o T-INFRA.1 tem bug real — escale imediatamente antes de continuar.
