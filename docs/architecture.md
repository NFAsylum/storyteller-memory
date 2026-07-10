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

### `core/llm_client.py`
Wrapper Anthropic SDK.
- `LlmClient.__init__(model="claude-sonnet-4-6", api_key)` — retry exponencial (max 3), timeout 60s, cost logging por chamada
- `generate(system, messages, tools=None) -> LlmResponse` — retorna `content`, `stop_reason`, `usage`, `cost_usd`
- Erros de rate limit (429) fazem backoff automático

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
Rotas mínimas:
- `POST /sessions` — cria nova sessão, retorna `session_id`
- `POST /sessions/{id}/turn` — envia input, retorna `TurnResult`
- `GET /sessions/{id}/state` — dump completo (memory + world state) para inspector
- `POST /sessions/{id}/reflect` — força reflection now
- `DELETE /sessions/{id}` — clear session

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
