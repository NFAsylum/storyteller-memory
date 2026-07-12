# Tasks — Storyteller

Formato: `[ ]` pendente, `[x]` feita. Nunca marcar feita se DoD não é 100% verificável. Nunca continuar próximo sprint sem "verificação final" do anterior aprovada.

**Total revisado: ~130 h.** Sprint 1-2 são "Fake wiring" — todo o esqueleto sem chamada LLM real. Sprint 3 (novo) é onde pela primeira vez plugamos Anthropic real + medimos baseline. Isso segue o padrão: infra + protocol + Fake → primeiro impl real + medição.

**Papel do LLM neste projeto:** o LLM é o **motor narrativo** — fixo, não vamos treinar. O trabalho é construir infra (memória, reflection, retrieval, harness) que faça o **mesmo** LLM performar melhor. O LLM é o sujeito da medição.

**Design principle:** `LlmClient` como Protocol. `FakeLlmClient` (respostas templadas, determinísticas) pra dev/testes. `AnthropicLlmClient` (Sprint 3+) pra medição real. Config switch via env var `LLM_BACKEND=fake|anthropic`.

---

## Sprint 1 — Skeleton + Fake wiring (20 h) — **ZERO API real**

### [x] S1.1 — Setup do projeto (3 h)
Criar estrutura: Poetry, dependências, `.env.example`. **SQLite** pra dev.
**DoD:** ✅ concluído

### [x] S1.2 — `core/llm_client.py` (3 h) — precisa retrofit
Wrapper Anthropic SDK com retry, timeout, cost logging.
**Retrofit necessário (blocker pra rodar sem API key):**
- Extrair `LlmClient` como Protocol em `core/llm_client.py`
- Renomear wrapper atual pra `AnthropicLlmClient` (impl do Protocol)
- Adicionar `FakeLlmClient` em `core/llm_fakes.py` — retorna resposta templada determinística baseada em hash do prompt
- Config switch: `create_llm_client()` factory lê `LLM_BACKEND` env var (default `fake` em dev)
- Testes atuais (mockados) continuam verdes; adicionar 3 testes pro FakeLlmClient
**DoD:**
- `LlmClient` Protocol definido com `.generate()` retornando `LlmResponse`
- `AnthropicLlmClient` e `FakeLlmClient` implementam o Protocol
- `create_llm_client()` respeita `LLM_BACKEND`
- Sem `ANTHROPIC_API_KEY` no env, `FakeLlmClient` funciona 100%
- `pytest tests/test_llm_client.py` verde (originais + 3 novos)

### [x] S1.3 — `core/story_loop.py` v1 (5 h) — retrofit + integração
Turn manager mínimo: input → LLM (via Protocol) → armazena em mem0.
**Nota:** código do story_loop já existe. Precisa apontar pro Protocol em vez do wrapper Anthropic direto. `scripts/manual_test.py` deve rodar com FakeLlmClient por default.
**DoD:**
- `StoryLoop.__init__` aceita `llm_client: LlmClient` (Protocol)
- `StoryLoop.run_turn(text)` retorna `TurnResult` com `narrator_text` não-vazio
- `scripts/manual_test.py` roda 5 turnos com FakeLlmClient (sem `ANTHROPIC_API_KEY` no env), prints determinísticos e legíveis
- Cada turn escreve entrada correspondente em mem0 (verificado via `mem0_adapter.list_all()` = 5 depois de 5 turnos)
- Testes com Fake substituem os mocks manuais (mais robusto)

### [x] S1.4 — Scenario/Question Pydantic models + loader (3 h)
Modelos pra representar cenários de teste. Ainda sem harness — só shape.
**DoD:**
- `Scenario` Pydantic model: `id, scenes: list[Scene], questions: list[Question]`
- `Scene`: `turn_id, user_input`
- `Question`: `id, asked_after_turn, category, question, ground_truth, acceptable_variants`
- `load_scenario(path) -> Scenario` valida JSON contra o model
- 3 testes: load válido, load com JSON malformado falha claro, load com pergunta sem ground_truth falha claro

### [x] S1.5 — 3 cenários seed (3 h)
Escrever `eval/scenarios/seed_01.json`, `seed_02.json`, `seed_03.json`. Cada um: 5 cenas, 10 perguntas cobrindo recall factual.
**DoD:**
- Cada JSON valida contra `Scenario` model (S1.4)
- Cada pergunta tem `ground_truth` e `category`
- Documentado em `eval/scenarios/README.md` como escrever novos

### [x] S1.6 — Manual test completo com Fake (3 h)
Verificar wiring end-to-end sem chamada real.
**DoD:**
- `scripts/manual_test.py`: cria session, roda 5 turnos com FakeLlmClient, imprime narrator_text de cada turn, imprime `mem0_adapter.list_all()` no fim
- Output é **determinístico** dado seed (5 execuções produzem output idêntico)
- Roda sem `ANTHROPIC_API_KEY` no env

### Verificação final Sprint 1
- [x] `pytest` inteiro verde (31 testes)
- [x] `unset ANTHROPIC_API_KEY && LLM_BACKEND=fake poetry run python scripts/manual_test.py` roda até o fim, imprime 5 turnos + list_all()
- [x] Nenhum acesso a API real durante toda a Sprint 1

---

## Sprint 2 — World state + reflection (Fake ainda) (20 h) — **ZERO API real**

Constrói mecânica de memória estruturada. Ainda com Fake — validamos estrutura, não qualidade.

### [x] S2.1 — Schema SQLite + migrations (4 h)
Criar tabelas via SQLAlchemy 2.0: `characters`, `locations`, `relations`, `story_beats`. Alembic pra migrations. **Tipos portáveis SQLite ↔ Postgres** (`JSON` genérico, não JSONB; sem ARRAY — traits/tags como JSON list).
**DoD:**
- `alembic upgrade head` cria as 4 tabelas no SQLite
- Seed script `scripts/seed_test_data.py` insere 3 personagens fake, roda sem erro
- `pytest tests/test_world_state.py` cobre CRUD básico das 4 entidades
- Nenhum tipo Postgres-only nas migrations (grep por `JSONB`, `ARRAY`, `postgresql.` retorna 0)

### [x] S2.2 — Reflection Protocol + FakeReflection (6 h)
`Reflection` como Protocol. Fake implementation retorna JSON estruturado determinístico baseado nos turnos.
**DoD:**
- `Reflection` Protocol: `consolidate(session_id, since_turn) -> ReflectionResult`
- `FakeReflection` extrai personagens de forma mecânica: qualquer palavra iniciada em maiúscula > 2x nos turnos vira personagem candidato (regra simples), grava em Postgres/SQLite
- `AnthropicReflection` fica pra Sprint 3 — não implementar ainda
- `ReflectionResult`: `beats_created, characters_updated, relations_updated, cost_usd`
- Prompt template em `core/prompts/reflection.txt` (usado só na Sprint 3)
- 5 testes: turnos vazios, turnos com 1 personagem, turnos com múltiplos, evento repetido não duplica, ReflectionResult tem contagens não-negativas

### [x] S2.3 — `core/memory/retrieval_policy.py` (4 h)
Bundle de contexto para próximo turn.
**DoD:**
- `RetrievalPolicy.build_context(session_id, turn, user_input)` retorna `ContextBundle` com 4 chaves populadas
- Estimativa de tokens em `token_estimate` (aproximação: 4 chars ≈ 1 token)
- Teste: dado session seed, retorna >0 memories e >0 active_characters

### [x] S2.4 — Integrar retrieval + reflection no story_loop (4 h)
Story_loop v2 usa `RetrievalPolicy` antes de chamar LLM. Prompt inclui context bundle. Reflection roda a cada 5 turnos.
**DoD:**
- `StoryLoop.run_turn()` chama `RetrievalPolicy.build_context()` e injeta no prompt (via FakeLlmClient)
- `TurnResult.retrieved_context` populado com o bundle
- Manual test de 15 turnos com Fake: reflection dispara em turns 5, 10, 15; world_state tem entries
- Turnos 6+ visivelmente referenciam eventos anteriores via bundle (mesmo com Fake, o bundle chega no prompt)

### [x] S2.5 — Manual test estrutural (2 h)
End-to-end sem LLM real. Verifica que os DADOS fluem certo.
**DoD:**
- `scripts/manual_test_sprint2.py`: 15 turnos com Fake → verifica: tabelas populadas, reflection disparou 3x, retrieval retornou >0 items nos últimos 10 turnos
- Output determinístico
- Nenhum `ANTHROPIC_API_KEY` no env

### Verificação final Sprint 2
- [x] `pytest` inteiro verde (52 testes)
- [x] `unset ANTHROPIC_API_KEY && poetry run python scripts/manual_test_sprint2.py` roda até o fim, mostra que world_state populou
- [x] Estrutura de dados verificada: characters/locations/relations/story_beats existem e têm registros

---

## Sprint 3 — Real LLM + first measurement (20 h) — **PRIMEIRA VEZ QUE PRECISA DE API KEY**

Onde plugamos Anthropic real e rodamos o primeiro baseline mensurável. Se você (marco) ainda não tem API key, esse é o momento — instância vai parar aqui e escalar.

### [x] S3.1 — Validar AnthropicLlmClient + config switch (3 h)
Wrapper já existe (S1.2). Aqui garantimos que roda contra API real com key válida.
**DoD:**
- `LLM_BACKEND=anthropic ANTHROPIC_API_KEY=sk-ant-... poetry run python scripts/smoke_llm.py "hello"` retorna resposta real
- Custo logado no output (~$0.001)
- Rate limit (429) faz backoff automático
- Timeout config funcional

> **Adaptado pro backend local (inbox 2026-07-11):** Sprint 3 roda com `LLM_BACKEND=local`. Validado com `scripts/smoke_llm.py` (genérico, agnóstico de backend) → resposta real do Qwen ("Blue.", ~5s, cost $0). Config switch fake/anthropic/local + inválido coberto no factory. O 429-backoff e o timeout→`LlmTimeoutError` do `AnthropicLlmClient` seguem cobertos pelos unit tests do S1.2 (wrapper inalterado). Rodar contra Anthropic real (custo ~$0.001) fica opcional pra quando houver key paga.

### [x] S3.2 — `AnthropicReflection` (4 h)
Impl real de `Reflection` Protocol. Prompt em `core/prompts/reflection.txt` gera JSON estruturado.
**DoD:**
- `AnthropicReflection.consolidate(...)` chama LLM real com prompt de reflection
- Response JSON valida contra schema estruturado (characters, locations, relations, beats)
- Retry se JSON malformado (max 2 retries com feedback)
- Teste manual: rodar em session de 10 turnos, verificar que story_beats populou com summaries reais
- Custo por reflection registrado (~$0.01-0.05)

> **Impl como `LlmReflection` (genérica, recebe `LlmClient`) em vez de `AnthropicReflection`** — roda com o backend configurado (local, per inbox). Verificado real: `LLM_BACKEND=local scripts/manual_reflection_test.py` → 10 turnos + reflection do Qwen → JSON válido, `story_beats` com 3 summaries reais, chars=3/locs=2/rels=3, cost $0 (local), 99s. Retry de JSON malformado (max 2 com feedback) implementado + unit-tested (12 testes de reflection). Custo Anthropic (~$0.01-0.05) é $0 no backend local.

### [x] S3.3 — `eval/harness.py` v1 (6 h)
Carrega scenario, roda N turnos, faz M perguntas, retorna métricas.
**DoD:**
- `harness.run_scenario(scenario, config)` retorna `ScenarioResult` com `recall_rate`, `avg_cost_usd`
- Recall check via LLM-as-judge simples (pergunta se `ground_truth` ou `acceptable_variants` aparecem)
- Config permite escolher backend (fake pra sanity check, anthropic pra medição real)
- `pytest tests/test_harness.py` cobre 1 mini-scenario com FakeLlm (rápido, determinístico)

### [x] S3.4 — `eval/judges.py` v1 (4 h)
LLM-as-judge pra recall check + hallucination detection.
**DoD:**
- `judge_recall(question, response) -> Literal["YES", "NO", "PARTIAL"]`
- `judge_hallucination(ground_truth, response) -> bool`
- Prompts em `eval/prompts/`
- Testado com mock em 3 casos por função

### [x] S3.5 — First baseline measurement (3 h)
Rodar harness com Anthropic real. Escrever `results.md`.
**DoD:**
- `LLM_BACKEND=anthropic poetry run python -m eval.run_all_scenarios --config=baseline_mem0_only` roda
- Idem com `--config=mem0_plus_reflection`
- `results.md` criado com:
  - `sprint 3 baseline (mem0 only): N of 30 recall (X%)`
  - `sprint 3 augmented (mem0 + reflection): N of 30 recall (Y%)`
  - `delta: +Zpp`
  - Custo total: $X.XX
- Se `delta < 5pp`, escala pro humano — decisão: mais tuning na reflection ou pivotar

### Verificação final Sprint 3
- [x] `results.md` existe com dois números medidos
- [x] Custo total do sprint documentado ($0 — modelo local, sem custo de API)
- [x] Se resultado for surpreendente (baseline muito baixo ou delta negativo), diagnóstico documentado

---

## Sprint 4 — Iteração + harness expandido (20 h)

### [x] S4.1 — Expandir para 30 perguntas / 5 cenários (6 h)
Cobrir 5 categorias:
- `recall_factual` (10)
- `character_consistency` (6)
- `relation_evolution` (6)
- `world_state` (4)
- `controlled_forgetting` (4)

**DoD:**
- `eval/scenarios/full/` tem 5 arquivos JSON
- Cada pergunta tem `category`
- Total 30 perguntas
- `poetry run python -m eval.count_questions` retorna 30

### [ ] S4.2 — Judges subjetivos (6 h)

> **Parcial (decisão C, 2026-07-11):** `judge_consistency(character_profile, response) -> float [0,1]` implementado + testado (mock). A **calibração** (`judges_calibration.json` com scores humanos + `calibrate_judges` + gate >80%) fica **adiada** até Marco fornecer os scores humanos de referência. Não marcar [x] até calibrar.
Expandir `judges.py` com consistency + hallucination detection subjetiva.
**DoD:**
- `judge_consistency(character_profile, response) -> float [0,1]`
- 5 exemplos manuais em `eval/judges_calibration.json` com score humano
- Rodar `poetry run python -m eval.calibrate_judges`: concordância humano/LLM >80%

### [x] S4.3 — Iterar prompt + retrieval (6 h)
Testar 4 variantes, medir cada uma.
**DoD:**
- Tabela em `docs/experiments.md` com 4 variantes (2 prompt + 2 retrieval)
- Cada linha: `variant_id, recall_rate, consistency_score, hallucination_rate, avg_cost_per_turn`
- Winner selecionado com justificativa
- Config vencedora salva como `configs/best.yaml`

### [ ] S4.4 — Documentar experiments (2 h)
**DoD:**
- `docs/experiments.md`: método, tabela, decisão, próximos experimentos
- README linka essa seção

### Verificação final Sprint 4
- [ ] Rodar `--config=configs/best.yaml` — número final que vai no portfólio
- [ ] Se abaixo do baseline do Sprint 3, algo quebrou — para e diagnostica
- [ ] Custo total do sprint documentado (esperado: $3-8)

---

## Sprint 5 — Frontend + memory inspector (20 h)

> **PIVOT (inbox 2026-07-11):** Streamlit → **Next.js 16 + shadcn (Base UI) + Tailwind 4 + Vitest**, construído do zero em `ui/`. O DoD abaixo foi reescrito pra bater com o da FASE 2 do inbox. Backend na branch `dev-marco-phase1-audit-fixes` (9 endpoints FastAPI + CORS + /health), frontend na branch `dev-marco-s5-ui` (empilhada). As sub-tasks Streamlit originais (S5.1-S5.4) ficam obsoletas.

### [x] S5.1 — Chat base (Next.js) — DONE
`ChatArea` + `SessionsSidebar` + persistência de session em cookie (30 d).
**DoD:**
- [x] `npm run build` OK; `npm run dev` sobe em :3000 (dev roda; verificação visual é do Marco)
- [x] Cookie de 30 dias: home resume a última sessão (`session-cookie.ts`)
- [x] Cada turno chama `POST /sessions/{id}/turn` (via `api.runTurn`)
- [x] Erro de API mostra toast (sonner), não crash — coberto por teste

### [x] S5.2 — Memory Inspector (Next.js) — DONE
4 abas com contagem: **Personagens / Locais / Relações / Story beats**.
**DoD:**
- [x] Cards de personagem (nome + traits + first_appeared_turn), locais, relações (id→nome), beats (timeline)
- [x] Contagem no header de cada aba (ex.: "Personagens (5)")
- [x] Popula em tempo real via SWR (revalidação após cada `POST /turn`)

### [x] S5.3 — Botões debug (Next.js) — DONE
`DebugPanel` abaixo do inspector:
- [x] `Forçar reflection` → `POST /sessions/{id}/reflect` (toast com contagens / falha)
- [x] `Contexto do último turno` → `GET /turns/{n}/context` (raw memories + facts + active chars)
- [x] `Comparar com/sem memória` → `POST /compare-turn`, split-screen (killer demo)
- [x] `Limpar sessão` → `DELETE /sessions/{id}` com modal de confirmação

### [x] S5.4 — Persistência de session — DONE
- [x] Session id em cookie 30 d; home reabre direto na sessão se ainda existe no backend
- [x] Backend registra `Session` + `Turn` (SQLite, migration 0002)

### Verificação final Sprint 5
- [x] `pytest` backend verde (101)
- [x] `npm run test` (Vitest) verde — 9 testes, 3 eixos (render/interação/erro-loading) por componente
- [x] Backend e2e via curl: health/CORS/create/turn/state/compare
- [ ] **BLOQUEADO (sem browser/DISPLAY na instância):** testar UI em navegador 30 min sem crash
- [ ] **BLOQUEADO:** 3-4 screenshots em `docs/screenshots/` + GIF em `docs/demo.gif` — Marco gera (ver `docs/screenshots/README.md`)

> Sprint 5 **não** marcada 100% feita: os 2 itens visuais dependem de browser (blocker escalado ao Marco). Todo o resto é verificável e verde.

---

## Sprint 6 — Deploy + polish + migração SQLite → Postgres (20 h)

### [ ] S6.1 — Dockerize backend + frontend (6 h)
**DoD:**
- `docker build -f Dockerfile.api .` produz imagem <500MB
- `docker build -f Dockerfile.ui .` produz imagem <300MB
- Smoke test passa contra API dockerizado

### [ ] S6.2 — Deploy Fly.io + migração SQLite → Postgres (8 h)
Momento planejado de trocar SQLite → Postgres.
**DoD:**
- Fly Postgres provisionado; `DATABASE_URL` prod aponta pra ele
- `alembic upgrade head` roda contra Postgres remoto (schema portável desde Sprint 2)
- Smoke: criar sessão, gerar 3 turnos, verificar persistência
- `fly deploy` sucede
- Secrets via `fly secrets`
- URL público responde `GET /health` com 200
- Dev local continua com SQLite

### [ ] S6.3 — README (5 h)
**DoD:**
- Seções: Problema, Arquitetura, Resultados do harness (tabela), Como rodar local, Deploy, Limitações
- Screenshot do Memory Inspector
- Reader externo roda local em <10 min

### [ ] S6.4 — Landing/GIF (3 h)
GIF de 20-30s mostrando recall cross-session.
**DoD:**
- GIF <5MB
- Mostra: sessão 1 (evento A), fecha, sessão 2 (LLM lembra de A)
- Embarcado no README

### [ ] S6.5 — Bugfixes e polish (4 h) — reservado do buffer geral
**DoD:**
- Rodar happy path por 30 min sem erro
- Warnings do pytest resolvidos
- Nenhum TODO/FIXME crítico

### Verificação final Sprint 6
- [ ] URL público funcional compartilhado
- [ ] README validado
- [ ] Números do harness embutidos no README

---

## Sprint 7 — Buffer + demo (10 h)

### [ ] S7.1 — Buffer dívidas técnicas (5 h)

### [ ] S7.2 — Demo video 2-3 min (3 h)
Roteiro: sessão 1 → fecha → sessão 2 uma semana depois (fake) → memory inspector → números do harness.
**DoD:**
- Video gravado, hospedado (Loom/YouTube)
- Link no README

### [ ] S7.3 — Post técnico curto (2 h)
LinkedIn + dev.to.
**DoD:**
- 300-500 palavras
- Números do harness citados
- Link pro repo e demo

---

## Estimativas resumidas

| Sprint | Total | Cumulativo | LLM real? |
|---|---:|---:|---:|
| 1 | 20 h | 20 h | Fake |
| 2 | 20 h | 40 h | Fake |
| 3 | 20 h | 60 h | **Sim** |
| 4 | 20 h | 80 h | Sim |
| 5 | 20 h | 100 h | Só demo |
| 6 | 20 h | 120 h | Só demo |
| 7 | 10 h | 130 h | Demo |
