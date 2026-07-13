# Arquitetura — Storyteller

## Visão geral

Sistema de turno: usuário envia ação → LLM continua a narrativa → sistema armazena o turno em duas camadas (mem0 raw + Postgres estruturado). Periodicamente, uma reflection sumariza episódios em fatos estruturados. Ao gerar próximo turno, o `retrieval_policy` injeta o contexto relevante.

```
                       ┌────────────────────────────┐
       User input ────▶│   story_loop.run_turn()    │
                       └──────────┬─────────────────┘
                                  │
                                  ▼
                       ┌────────────────────────────┐
                       │   retrieval_policy.build   │────▶ Context bundle
                       │   ({session, turn}) ────▶  │      { raw_memories,
                       └──────────┬─────────────────┘        structured_facts,
                                  │                          active_characters }
                                  ▼
                       ┌────────────────────────────┐
                       │   llm_client.continue()    │
                       └──────────┬─────────────────┘
                                  │
                                  ▼
                       ┌────────────────────────────┐
                       │   Store turn:              │
                       │   - mem0_adapter.add()     │──▶ vector store
                       │   - world_state.record()   │──▶ Postgres
                       └──────────┬─────────────────┘
                                  │
                                  ▼
                            Response to user

     Every N turns (async or on-demand):
                       ┌────────────────────────────┐
                       │   reflection.consolidate() │
                       │   ├─ summarize episode     │
                       │   ├─ update characters     │
                       │   ├─ update relations      │
                       │   └─ store story_beats     │
                       └────────────────────────────┘
```

## Módulos

### `core/llm_client.py` — Protocol

`LlmClient` é `Protocol`. Duas impls:

```python
class LlmClient(Protocol):
    def generate(
        self,
        system: str,
        messages: list[dict],
        tools: list | None = None,
    ) -> LlmResponse: ...

class LlmResponse(BaseModel):
    content: str
    stop_reason: str
    usage: dict
    cost_usd: float
```

- **`FakeLlmClient` (`core/llm_fakes.py`)**: retorna resposta templada determinística, hash do prompt como seed. `cost_usd=0`. Sem API key. Sprints 1-2 rodam 100% com Fake.
- **`AnthropicLlmClient` (`core/llm_anthropic.py`)**: wrapper Anthropic SDK. Retry exponencial (max 3), timeout 60s, cost logging, backoff em 429. Precisa de `ANTHROPIC_API_KEY`. Ativado em Sprint 3+.

Factory: `create_llm_client()` em `core/llm_client.py` lê env `LLM_BACKEND` (default `fake`) e retorna a impl correta. `LocalLlmClient` (`core/llm_local.py`) fala com um llama-server OpenAI-compatible (`LOCAL_LLM_URL`), `cost_usd=0`.

**Reprodutibilidade (F1.5):** os backends reais rodam com **`temperature=0`** e, no local, **`seed=42`** (via `LOCAL_LLM_SEED`), pra que rodadas do harness sejam determinísticas run-a-run. `FakeLlmClient` já é determinístico por construção.

Mesma lógica pra `Reflection`: `Reflection` Protocol + `FakeReflection` (regra determinística) + `AnthropicReflection` (Sprint 3, LLM sumariza).

### `core/story_loop.py`
Coordena um turno.
- `StoryLoop(session_id, memory, world_state, llm)` — construtor
- `run_turn(user_input: str) -> TurnResult` — orquestra retrieval + LLM + store
- `TurnResult`: `narrator_text`, `retrieved_context`, `stored_memory_ids`, `cost_usd`

### `core/memory/mem0_adapter.py`
Fachada sobre mem0. Isola dependência.
- `Mem0Adapter(session_id)` — inicializa
- `add(text: str, metadata: dict) -> memory_id`
- `search(query: str, top_k: int = 5) -> list[Memory]`
- `list_all() -> list[Memory]`
- `clear()` — apaga memórias da session

### `core/memory/world_state.py`
CRUD SQLAlchemy 2.0 para estado estruturado. Backend SQLite no dev, Postgres na prod (Sprint 5). Schemas usam apenas tipos portáveis (nenhum JSONB/ARRAY — `JSON` genérico só).

Schemas (SQLAlchemy):
- `characters(id, session_id, name, traits: list[str], first_appeared_turn: int, last_seen_turn: int)`
- `locations(id, session_id, name, description, first_visited_turn: int)`
- `relations(id, session_id, a_character_id, b_character_id, kind: str, valence: int, since_turn: int)`
- `story_beats(id, session_id, summary, turn, importance: int, tags: list[str])`

Funções:
- `record_turn_entities(session_id, turn, extracted: dict)` — cria/atualiza entidades mencionadas
- `top_facts(session_id, query_context: str, k: int = 5) -> list[Beat]`
- `active_characters(session_id, recent_turns: int = 10) -> list[Character]`

### `core/memory/reflection.py`
Roda a cada N turnos (default 5) ou sob demanda.
- `Reflection(llm, world_state, memory)`
- `consolidate(session_id, since_turn: int) -> ReflectionResult`
  - Puxa turnos desde `since_turn`
  - LLM sumariza em JSON estruturado (chars/rels/locations/beats)
  - Persiste em world_state
- `ReflectionResult`: `beats_created`, `characters_updated`, `relations_updated`, `cost_usd`

### `core/memory/retrieval_policy.py`
Decide o que injetar no próximo prompt.
- `build_context(session_id, current_turn: int, user_input: str) -> ContextBundle`
- Estratégia default:
  - Top 5 do mem0 por similaridade com `user_input`
  - Top 3 story_beats mais recentes com alta importância
  - Todos os `active_characters` dos últimos 10 turnos
  - Locations mencionados no user_input via NER simples (regex por nome próprio inicial)
- `ContextBundle`: `raw_memories`, `structured_facts`, `active_characters`, `token_estimate`

### `eval/harness.py`
Roda cenário e retorna métricas.
- `Scenario(scenes: list[Scene], questions: list[Question])` — carregado de JSON
- `run_scenario(scenario, config: HarnessConfig) -> ScenarioResult`
- Métricas: `recall_rate`, `consistency_score`, `hallucination_rate`, `avg_cost_usd`
- Baseline: mesma execução com memória desabilitada (LLM só recebe user input)

### `eval/judges.py`
LLM-as-judge para métricas subjetivas.
- `judge_consistency(character_profile, generated_text) -> float [0, 1]`
- `judge_hallucination(ground_truth, generated_text) -> bool`
- Concordância humano/LLM tem que ser >80% em 5 exemplos manuais (testado no Sprint 3)

### `api/` (FastAPI)
Rotas:
- `GET /sessions` / `POST /sessions` / `GET /sessions/{id}` / `DELETE /sessions/{id}`
- `POST /sessions/{id}/turn` — envia input, retorna `TurnResult`
- `GET /sessions/{id}/turns/{n}/context` — `ContextBundle` usado naquele turno
- `POST /sessions/{id}/reflect` — força reflection now
- `POST /sessions/{id}/compare-turn` — reexecuta o último turno `no_memory` vs `mem0_only`
- `GET /sessions/{id}/state` — world_state + `raw_memory_count` + `next_reflection_at`
- `GET /sessions/{id}/raw-memories` — memórias brutas do mem0 por turno (estado pré-reflection)

**Operacional (T1.3):**
- `GET /health` → `{status, backend_llm, mem0_ready, db_ready}` (sempre 200; `status="degraded"` se mem0/DB indisponível). Isento de rate limit — usado por healthcheck do Fly.
- **CORS:** origens permitidas via env **`CORS_ORIGINS`** (CSV; default `http://localhost:3000`). Padronizado — não usar `ALLOWED_ORIGINS`.
- **Rate limit:** in-memory por IP, janela deslizante de 60s, `RATE_LIMIT_PER_MINUTE` (default 60); o request (limite+1) recebe 429. Estado process-local (ok para instância única de dev).
- **Reprodutibilidade (F1.5):** backends LLM rodam com `temperature=0`; o local também com `seed=42` (`LOCAL_LLM_SEED`).

### `ui/` (Streamlit)
- Chat na área principal
- Sidebar Memory Inspector com abas: `Memories` (raw mem0), `World State` (chars/locs/rels), `Reflections` (story_beats)
- Botões debug: force reflection, show retrieved this turn, clear session
- Session ID persistido em cookie do browser

## Fluxo de dados de teste (eval)

```
scenarios/*.json  →  harness.load(scenario)
                     harness.run(scenario, config)
                     ├─ Runs N story turns per scene
                     ├─ Asks M questions after all scenes
                     └─ Judges answers vs ground_truth
                     → ScenarioResult { recall_rate, ... }

harness.run(scenario, config_baseline)  → baseline_result
Compare → delta report
```

Formato de `Scenario` (JSON):
```json
{
  "id": "escala-castelo-01",
  "scenes": [
    { "turn_id": 1, "user_input": "Introduzo Aria como cavaleira leal ao rei." },
    { "turn_id": 2, "user_input": "Aria descobre traição do conselheiro Vex." }
  ],
  "questions": [
    {
      "id": "q1",
      "asked_after_turn": 10,
      "category": "recall_factual",
      "question": "Quem descobriu a traição de Vex?",
      "ground_truth": "Aria",
      "acceptable_variants": ["a cavaleira Aria", "Aria, a cavaleira"]
    }
  ]
}
```

## Convenções de código

- Python 3.11, type hints obrigatórios em funções públicas
- Pydantic v2 para models
- SQLAlchemy 2.0 sintaxe (não legacy)
- Sem `async` desnecessário no MVP — FastAPI aceita sync handlers
- Docstring em inglês, uma linha, WHY quando não óbvio
- Não escrever comentários que apenas descrevem o que o código já diz
