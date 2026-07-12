# FastAPI sem CORS e sem endpoint `/health`

**Severity:** High
**Priority:** P1 (bloqueia Sprint 5 + Sprint 6)
**Category:** UX / Design
**Source:** `api/main.py:39` (declaração do `FastAPI(...)` sem middlewares)

## Descrição

Duas lacunas complementares:

1. **Nenhum `CORSMiddleware` registrado.** Grep por `CORS`, `allow_origins`,
   `allow_methods` retorna 0 matches no repo inteiro. A criação do app é uma
   linha só:
   ```python
   app = FastAPI(title="Storyteller API")
   ```

2. **Nenhum endpoint `/` ou `/health`.** Os 9 endpoints declarados começam em
   `/sessions`. `docs/tasks.md:287` (Sprint 6 DoD) explicitamente lista:
   > URL público responde `GET /health` com 200

## Risco

**Sprint 5 (UI Next.js)** — a UI planejada roda em `http://localhost:3000` e
faz fetch para `http://localhost:8000/sessions/*`. Sem CORS, o browser bloqueia
todas as requisições XHR/fetch com `CORS error: no 'Access-Control-Allow-Origin' header`.
UI não consegue carregar dados, criar sessão, ou disparar turn. Bloqueia
o desenvolvimento inteiro do Sprint 5.

**Sprint 6 (deploy Fly.io)** — Fly configura healthcheck automático em `/health`.
Sem esse endpoint, a instância nunca fica "healthy" e o loadbalancer não roteia
tráfego. Deploy aparenta subir mas responde 502.

Impacto secundário: sem `/`, o URL raiz responde `{"detail":"Not Found"}` — má
first impression para quem abre o link.

## Fix sugerido

Adição mínima em `api/main.py`, logo depois de `app = FastAPI(...)`:

```python
import os
from fastapi.middleware.cors import CORSMiddleware

_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "storyteller", "docs": "/docs"}
```

Notas de produção:
- Em prod (Fly.io), `CORS_ALLOWED_ORIGINS` restringe a origem específica do
  frontend. Nunca `["*"]` com `allow_credentials=True` (browser rejeita).
- `/health` pode virar smoke check leve (verifica conexão DB) — mas começar
  simples é aceitável.

Adicionar teste:
```python
def test_health_returns_ok(client):
    tc, _ = client
    assert tc.get("/health").json() == {"status": "ok"}

def test_cors_headers_present(client):
    tc, _ = client
    resp = tc.options(
        "/sessions",
        headers={"Origin": "http://localhost:3000",
                 "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
```

## Referências

- FastAPI CORS: https://fastapi.tiangolo.com/tutorial/cors/
- Fly.io health checks: https://fly.io/docs/reference/configuration/#the-checks-section
