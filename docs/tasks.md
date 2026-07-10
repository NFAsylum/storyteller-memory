# Tasks — Storyteller

Formato: `[ ]` pendente, `[x]` feita. Nunca marcar feita se DoD não é 100% verificável. Nunca continuar próximo sprint sem "verificação final" do anterior aprovada.

Total: 110 h. Ordem sequencial dentro do sprint, mas tarefas dentro do mesmo sprint podem ser feitas em paralelo se não têm dependência.

---

## Sprint 1 — Fundação mensurável (20 h)

### [ ] S1.1 — Setup do projeto (3 h)
Criar estrutura: Poetry, dependências, docker-compose.yml com Postgres, .env.example.
**DoD:**
- `docker compose up -d` sobe Postgres na porta 5432
- `poetry install` termina sem erro
- `poetry run pytest` executa (0 testes por enquanto, mas exit code 0)
- `.env.example` lista `ANTHROPIC_API_KEY`, `DATABASE_URL`

### [ ] S1.2 — `core/llm_client.py` (3 h)
Wrapper Anthropic SDK com retry, timeout, cost logging.
**DoD:**
- `tests/test_llm_client.py` cobre: chamada sucesso, retry após 429 (mock), timeout retorna erro específico
- `LlmClient.generate()` retorna `LlmResponse` com `cost_usd` calculado (input tokens × price + output × price, tabela hardcoded)
- `pytest tests/test_llm_client.py` verde

### [ ] S1.3 — `core/story_loop.py` v1 (5 h)
Turn manager mínimo: input → LLM → armazena em mem0 (sem world state ainda).
**DoD:**
- `StoryLoop.run_turn(text)` retorna `TurnResult` com `narrator_text` não-vazio
- Script `scripts/manual_test.py` roda 5 turnos consecutivos numa session, prints legíveis
- Cada turn escreve entrada correspondente em mem0 (verificado via `mem0_adapter.list_all()`)

### [ ] S1.4 — `eval/harness.py` v1 (6 h)
Carrega scenario JSON, roda N turnos, faz M perguntas, retorna métricas.
**DoD:**
- `harness.run_scenario(scenario, config)` retorna `ScenarioResult` com `recall_rate` calculado
- Recall check: LLM-as-judge simples (pergunta se `ground_truth` ou `acceptable_variants` aparecem na resposta)
- `pytest tests/test_harness.py` cobre 1 mini-scenario end-to-end

### [ ] S1.5 — 3 cenários seed (3 h)
Escrever `eval/scenarios/seed_01.json`, `seed_02.json`, `seed_03.json`. Cada um: 5 cenas, 10 perguntas cobrindo recall factual.
**DoD:**
- Cada JSON valida contra `Scenario` Pydantic model
- Cada pergunta tem `ground_truth` e `category`
- Documentado em `eval/scenarios/README.md` como escrever novos

### Verificação final Sprint 1
- [ ] Rodar `poetry run python -m eval.run_all_scenarios --config=baseline_mem0_only`
- [ ] Gravar resultado em `results.md` (criar arquivo)
- [ ] Format: `sprint 1 baseline: N of 30 recall (X%)`
- [ ] Se `recall < 40%`, **para e escala pro humano** — mem0 pode estar mal configurado

---

## Sprint 2 — World state + reflection (20 h)

### [ ] S2.1 — Schema Postgres + migrations (4 h)
Criar tabelas: `characters`, `locations`, `relations`, `story_beats`. Usar Alembic.
**DoD:**
- `alembic upgrade head` cria as 4 tabelas
- Seed script `scripts/seed_test_data.py` insere 3 personagens fake, roda sem erro
- `pytest tests/test_world_state.py` cobre CRUD básico das 4 entidades

### [ ] S2.2 — `core/memory/reflection.py` (8 h)
A cada 5 turnos, LLM sumariza episódio em JSON estruturado, persiste em world_state.
**DoD:**
- `Reflection.consolidate(session_id, since_turn)` retorna `ReflectionResult` com contagens não-negativas
- Prompt de reflection em `core/prompts/reflection.txt`
- Teste: mock LLM retorna JSON estruturado; teste verifica que 2 personagens e 1 relation foram criados
- Script `scripts/manual_reflection_test.py` roda em session real, verifica que story_beats foi populado

### [ ] S2.3 — `core/memory/retrieval_policy.py` (4 h)
Bundle de contexto para próximo turn.
**DoD:**
- `RetrievalPolicy.build_context(session_id, turn, user_input)` retorna `ContextBundle` com 4 chaves populadas
- Estimativa de tokens em `token_estimate` (aproximação: 4 chars ≈ 1 token)
- Teste: dado session seed, retorna >0 memories e >0 active_characters

### [ ] S2.4 — Integrar retrieval no story_loop (4 h)
Story_loop v2 usa retrieval_policy antes de chamar LLM. Prompt inclui context bundle.
**DoD:**
- `StoryLoop.run_turn()` agora chama `RetrievalPolicy.build_context()` e injeta no prompt
- `TurnResult.retrieved_context` populado com o bundle usado
- Manual test de 15 turnos: turns 6+ visivelmente referenciam eventos dos turns 1-5

### Verificação final Sprint 2
- [ ] Rodar `poetry run python -m eval.run_all_scenarios --config=mem0_plus_reflection`
- [ ] Gravar delta em `results.md`
- [ ] Format: `sprint 2: N of 30 recall (X%), delta vs baseline: +Ypp`
- [ ] Se `delta < 5pp`, **para e escala** — decisão: investir mais em custom OU pivotar pra Zep (custo estimado do pivô: ~15 h)

---

## Sprint 3 — Harness formal + iteração (20 h)

### [ ] S3.1 — Expandir para 30 perguntas / 5 cenários (6 h)
Cobrir 5 categorias:
- `recall_factual` (10 perguntas)
- `character_consistency` (6)
- `relation_evolution` (6)
- `world_state` (4)
- `controlled_forgetting` (4)

**DoD:**
- `eval/scenarios/full/` tem 5 arquivos JSON
- Cada pergunta tem `category` de uma das 5 acima
- Total 30 perguntas somando todos os cenários
- `poetry run python -m eval.count_questions` retorna 30

### [ ] S3.2 — `eval/judges.py` (6 h)
LLM-as-judge para métricas subjetivas.
**DoD:**
- `judge_consistency(character_profile, generated_text) -> float [0,1]`
- `judge_hallucination(ground_truth, generated_text) -> bool`
- 5 exemplos manuais em `eval/judges_calibration.json` com score humano
- Rodar `poetry run python -m eval.calibrate_judges`: mostra concordância humano/LLM; **DoD: >80%**

### [ ] S3.3 — Iterar prompt + retrieval (6 h)
Testar 4 variantes de prompt/policy; medir cada uma.
**DoD:**
- Tabela em `docs/experiments.md` com 4 variantes:
  - Variantes de system prompt (2)
  - Variantes de estratégia de retrieval (2)
- Cada linha: `variant_id`, `recall_rate`, `consistency_score`, `hallucination_rate`, `avg_cost_per_turn`
- Winner selecionado com justificativa (1 parágrafo)
- Config vencedora salva como `configs/best.yaml`

### [ ] S3.4 — Documentar experiments (2 h)
**DoD:**
- `docs/experiments.md` tem: método, tabela de resultados, decisão final, próximos experimentos sugeridos
- README linka essa seção

### Verificação final Sprint 3
- [ ] Rodar `poetry run python -m eval.run_all_scenarios --config=configs/best.yaml`
- [ ] Gravar em `results.md`: número final que vai no portfólio
- [ ] Se abaixo do baseline do Sprint 1, algo quebrou — para e diagnostica

---

## Sprint 4 — Frontend + memory inspector (20 h)

### [ ] S4.1 — Streamlit chat base (6 h)
Chat mensagens + input + session_id persistente em cookie.
**DoD:**
- `streamlit run ui/app.py` abre chat funcional
- Recarregar página mantém a session (cookie válido por 30 dias)
- Cada mensagem chama `POST /sessions/{id}/turn`
- Erros de API mostram toast, não crashe

### [ ] S4.2 — Sidebar Memory Inspector (8 h)
3 abas: `Memories`, `World State`, `Reflections`.
**DoD:**
- Aba `Memories`: lista raw memories do mem0 com timestamp, similaridade com último turn
- Aba `World State`: tabelas de chars/locs/rels/beats, filtro por session
- Aba `Reflections`: story_beats agrupados por batch de reflection
- Cada aba tem botão refresh que re-fetcha via API

### [ ] S4.3 — Botões debug (4 h)
Sidebar tem 3 botões:
- `Force reflection now` → `POST /sessions/{id}/reflect`
- `Show retrieved this turn` → expander com último `ContextBundle`
- `Clear session` → `DELETE /sessions/{id}` + reload

**DoD:**
- Cada botão executa e mostra feedback visual (success/error)
- Confirmação modal em `Clear session`

### [ ] S4.4 — Persistência de session (2 h)
Autosave + resume: fechar e reabrir mantém contexto.
**DoD:**
- Teste manual: encerra Streamlit, reabre 24h depois (fake via env), context preservado
- Session record em Postgres tem `last_active_at` atualizado a cada turno

### Verificação final Sprint 4
- [ ] Testar UI em navegador por 30 min sem crash
- [ ] Fazer walkthrough gravado do memory inspector (screenshot ou GIF)
- [ ] Adicionar screenshot no `README.md` (criar se não existe)

---

## Sprint 5 — Deploy + polish (20 h)

### [ ] S5.1 — Dockerize backend + frontend (6 h)
Multi-stage Dockerfiles.
**DoD:**
- `docker build -f Dockerfile.api .` produz imagem <500MB
- `docker build -f Dockerfile.ui .` produz imagem <300MB
- `docker compose up` sobe API + UI + Postgres em modo dev
- Testes de smoke passam contra API dockerizado

### [ ] S5.2 — Deploy Fly.io (6 h)
API + UI + Fly Postgres.
**DoD:**
- `fly.toml` para API + UI
- `fly deploy` sucede sem erros
- `fly secrets set ANTHROPIC_API_KEY=... DATABASE_URL=...` — nenhuma secret em código
- URL público responde `GET /health` com 200

### [ ] S5.3 — README (5 h)
**DoD:**
- Seções: Problema, Arquitetura, Resultados do harness (tabela), Como rodar local, Como deployar, Limitações conhecidas
- Screenshot do Memory Inspector
- Reader externo consegue rodar local em <10 min seguindo o README
- Testar: pedir pra alguém não-familiarizado seguir README

### [ ] S5.4 — Landing/GIF (3 h)
Cria GIF de 20-30s mostrando recall cross-session.
**DoD:**
- GIF <5MB
- Mostra: sessão 1 (evento A), fecha, sessão 2 (LLM lembra de A)
- Embarcado no README

### [ ] S5.5 — Bugfixes e polish (4 h)
**DoD:**
- Rodar happy path por 30 min sem erro
- Todos os warnings do pytest resolvidos
- Nenhum TODO/FIXME crítico no código

### Verificação final Sprint 5
- [ ] URL público funcional compartilhado com humano
- [ ] README validado
- [ ] Números do harness embarcados no README

---

## Sprint 6 — Buffer + demo (10 h)

### [ ] S6.1 — Buffer dívidas técnicas (5 h)
Endereçar qualquer TODO acumulado ou bug relatado.

### [ ] S6.2 — Demo video 2-3 min (3 h)
Roteiro: sessão 1 → fecha → sessão 2 uma semana depois (fake) → mostra memory inspector → mostra números do harness.
**DoD:**
- Video gravado, hospedado (Loom/YouTube)
- Link no README

### [ ] S6.3 — Post técnico curto (2 h)
LinkedIn + dev.to.
**DoD:**
- 300-500 palavras
- Números do harness citados
- Link pro repo e demo

---

## Estimativas resumidas

| Sprint | Total | Cumulativo |
|---|---:|---:|
| 1 | 20 h | 20 h |
| 2 | 20 h | 40 h |
| 3 | 20 h | 60 h |
| 4 | 20 h | 80 h |
| 5 | 20 h | 100 h |
| 6 | 10 h | 110 h |
