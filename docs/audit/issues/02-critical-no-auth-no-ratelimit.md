# API pública sem autenticação nem rate limit

**Severity:** Critical
**Priority:** P0 (antes do Sprint 6 / deploy Fly.io)
**Category:** Security
**Source:** `api/main.py` (9 endpoints), `api/deps.py`

## Descrição

O FastAPI expõe 9 rotas e nenhuma exige autenticação. Não há middleware de rate
limit nem verificação de ownership de `session_id`.

Endpoints atuais (`api/main.py`):
```
GET    /sessions                              (linha 85-92)
POST   /sessions                              (linha 95-101)
GET    /sessions/{id}                         (linha 104-123)
DELETE /sessions/{id}                         (linha 126-134)
POST   /sessions/{id}/turn                    (linha 137-170)
GET    /sessions/{id}/turns/{n}/context       (linha 173-181)
POST   /sessions/{id}/reflect                 (linha 184-196)
POST   /sessions/{id}/compare-turn            (linha 199-230)
GET    /sessions/{id}/state                   (linha 233-237)
```

Nenhum recebe `Depends(get_current_user)`. Não há `Session.owner_id` no schema
(`world_state.Session` tem apenas `id`, `name`, `brief`, `created_at`, `last_turn`).

## Risco

Deploy do Sprint 6 planeja Fly.io público (`docs/tasks.md:281-287`). Cenários:

1. **Session hijack**: qualquer pessoa que descubra um `session_id` (16 hex chars,
   64 bits — ver issue 21) pode ler todos os turnos alheios via `GET /sessions/{id}`,
   apagar via `DELETE`, ou enviar turnos falsos via `POST /turn`.

2. **DoS financeiro (quando backend for Anthropic)**: `POST /sessions/{id}/turn`
   chama o LLM. Sem rate limit, um atacante pode disparar 10k requisições e
   torrar a cota Anthropic do dono. Custo por turno documentado ~$0.001 → 10k
   requisições ≈ $10 num único ataque; multi-hora ≈ $1000+.

3. **DoS computacional (backend local)**: cada turno roda o embedder + retrieval
   + LLM local. Requests concorrentes esgotam CPU/GPU do host.

4. **`POST /reflect` amplificação**: `LlmReflection.consolidate(since_turn=0)`
   processa TODOS os turnos da sessão — quanto mais turnos, mais tokens.
   Atacante pode fazer reflection sobre sessões grandes repetidamente.

5. **Enumeração de sessões**: `GET /sessions` retorna a lista completa
   (linha 88: `select(Session).order_by(Session.created_at.desc())`). Sem filtro
   por owner, todo mundo vê tudo.

## Fix sugerido

Mínimo viável para deploy público:

1. **Adicionar `owner_id` a `Session`** (via nova migration Alembic):
   ```python
   owner_id: Mapped[str] = mapped_column(String(64), index=True)
   ```

2. **API key simples** (esconder as rotas atrás de um header):
   ```python
   from fastapi.security import APIKeyHeader
   api_key_header = APIKeyHeader(name="X-API-Key")

   def verify_api_key(key: str = Depends(api_key_header)) -> str:
       expected = os.environ["STORYTELLER_API_KEY"]
       if key != expected:
           raise HTTPException(401, "invalid api key")
       return key
   ```
   Aplicar em cada endpoint via `Depends(verify_api_key)`.

3. **Rate limit** com `slowapi` (biblioteca leve compatível com FastAPI):
   ```python
   from slowapi import Limiter, _rate_limit_exceeded_handler
   limiter = Limiter(key_func=get_remote_address)
   @app.post("/sessions/{id}/turn")
   @limiter.limit("10/minute")
   ...
   ```

4. **`GET /sessions` filtrado por owner** (não vazar lista).

5. **CORS restrito** por origem (ver issue 06 também).

Se o projeto **não vai virar público** (apenas demo local), documentar isso
explicitamente em `docs/tasks.md` — reduzir severidade pra High.

## Referências

- OWASP API Security Top 10 (Broken Function Level Authorization): https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/
- slowapi: https://slowapi.readthedocs.io/en/latest/
