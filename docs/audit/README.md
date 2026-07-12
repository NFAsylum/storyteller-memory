# Auditoria Storyteller — 2026-07-11

Auditoria completa do projeto Storyteller (LLM com memória de longo prazo verificável)
conforme o brief da diretiva. Cobre design/arquitetura, bugs lógicos, guidelines,
segurança, performance, UX, testes e eval/harness.

## Sumário por severidade

| Severity | Contagem |
|---|---:|
| Critical | 3 of 22 findings |
| High     | 7 of 22 findings |
| Medium   | 8 of 22 findings |
| Low      | 4 of 22 findings |
| Total    | 22 of 22 findings |

## Top 5 riscos

1. **Prompt injection sem mitigação** — o `user_input` vai literalmente pro prompt do
   `story_continuation.txt` e é gravado em mem0 verbatim. Nada sanitiza ou detecta
   ataques. Se a API do Sprint 5 for pública (Fly.io), qualquer usuário pode fazer o
   narrador ignorar as regras. Ver `01-critical-prompt-injection.md`.

2. **FastAPI sem autenticação nem rate-limit** — os 9 endpoints em `api/main.py`
   aceitam qualquer requisição sem `Depends(current_user)` nem middleware de auth.
   Qualquer cliente pode ler/escrever qualquer `session_id`. Deploy público (Sprint 6)
   vira surface de abuse trivial. Ver `02-critical-no-auth-no-ratelimit.md`.

3. **Recall judge por substring cria falsos-positivos silenciosos** —
   `simple_recall_judge` faz `_normalize(needle) in _normalize(haystack)`. Ground truths
   curtos (ex. "Vex", "Aria") batem em qualquer palavra que os contenha como substring
   ("Vexado", "Ariana"). Como o número-manchete "0% → 90%" é o resultado do portfólio,
   uma métrica frouxa mina a credibilidade da medição. Ver `03-high-substring-recall-judge.md`.

4. **`class Session` em `core/memory/world_state.py` sombreia `sqlalchemy.orm.Session`**
   — a type hint em `WorldState.__init__(self, session: Session)` na verdade referencia
   o modelo ORM, não a Session do SQLAlchemy. mypy quebra em silêncio; refactor futuro
   passa objeto errado sem warning. Ver `04-high-session-shadow.md`.

5. **CORS não habilitado + `GET /health` ausente** — o Sprint 5 é UI Next.js em outra
   porta que vai chamar o backend via fetch. Sem `CORSMiddleware`, todas as chamadas
   browser são bloqueadas. Fly.io também espera `GET /health` para healthcheck; hoje
   retorna 404. Ver `06-high-cors-and-health-missing.md`.

## Índice de issues

### Critical (P0)
1. [01-critical-prompt-injection.md](issues/01-critical-prompt-injection.md) — user_input entra direto no prompt do LLM sem sanitização
2. [02-critical-no-auth-no-ratelimit.md](issues/02-critical-no-auth-no-ratelimit.md) — API pública sem autenticação nem rate limit
3. [03-critical-substring-recall-judge.md](issues/03-critical-substring-recall-judge.md) — `simple_recall_judge` é substring match ingênuo — falsos-positivos no número-manchete

### High (P1)
4. [04-high-session-shadow.md](issues/04-high-session-shadow.md) — `class Session` sombreia `sqlalchemy.orm.Session` no type hint
5. [05-high-story-beat-duplication-on-rerun.md](issues/05-high-story-beat-duplication-on-rerun.md) — `FakeReflection`/`LlmReflection` não deduplicam story_beats em reruns
6. [06-high-cors-and-health-missing.md](issues/06-high-cors-and-health-missing.md) — FastAPI sem CORS e sem `/health`
7. [07-high-delete-session-mem0-inconsistency.md](issues/07-high-delete-session-mem0-inconsistency.md) — `DELETE /sessions/{id}` commita DB antes de limpar mem0 (inconsistência)
8. [08-high-nondeterministic-local-llm.md](issues/08-high-nondeterministic-local-llm.md) — `LocalLlmClient` não fixa temperature/seed — resultados variam entre runs
9. [09-high-silent-reflection-json-failure.md](issues/09-high-silent-reflection-json-failure.md) — `LlmReflection` engole falha após 2 retries sem log
10. [10-high-n1-relations-dedupe.md](issues/10-high-n1-relations-dedupe.md) — `LlmReflection._persist_relations` executa `world.list(Relation, ...)` dentro do loop (N+1)

### Medium (P2)
11. [11-medium-doc-drift-anthropic-reflection.md](issues/11-medium-doc-drift-anthropic-reflection.md) — `docs/architecture.md` diz `AnthropicReflection`; código tem `LlmReflection`
12. [12-medium-run-scenario-does-not-reset-world.md](issues/12-medium-run-scenario-does-not-reset-world.md) — `run_scenario` limpa mem0 mas não `world_state` — contaminação entre reruns dentro do mesmo processo
13. [13-medium-anthropic-key-forwarded-to-mem0.md](issues/13-medium-anthropic-key-forwarded-to-mem0.md) — `ANTHROPIC_API_KEY` real é forwardado ao mem0 mesmo com `infer=False`
14. [14-medium-embed-per-question-no-cache.md](issues/14-medium-embed-per-question-no-cache.md) — embed rodado a cada pergunta no harness sem cache
15. [15-medium-consistency-judge-fed-garbage-profile.md](issues/15-medium-consistency-judge-fed-garbage-profile.md) — `judge_consistency` recebe `{traits: [ground_truth], backstory: question}` como perfil — não mede consistência real
16. [16-medium-shared-mem0-storage-cross-run.md](issues/16-medium-shared-mem0-storage-cross-run.md) — FAISS store `./.mem0_data` acumula em runs; sessões antigas ficam órfãs
17. [17-medium-portuguese-in-code-identifier.md](issues/17-medium-portuguese-in-code-identifier.md) — `_COOCCURRENCE = "co-ocorrencia"` viola "inglês em código"
18. [18-medium-test-count-mismatch.md](issues/18-medium-test-count-mismatch.md) — brief diz 70 testes; arquivos definem 78 — doc/estado desalinhado

### Low (P3)
19. [19-low-vague-fake-narration-language-lock.md](issues/19-low-vague-fake-narration-language-lock.md) — `FakeLlmClient` sempre em português (não respeita user_input)
20. [20-low-recall-judge-normalization.md](issues/20-low-recall-judge-normalization.md) — `_normalize` sem strip de pontuação — "Aria." não bate "Aria"
21. [21-low-uuid-truncated-to-16-hex.md](issues/21-low-uuid-truncated-to-16-hex.md) — `session_id = uuid.uuid4().hex[:16]` (64 bits em vez de 128)
22. [22-low-code-nitpicks.md](issues/22-low-code-nitpicks.md) — nitpicks consolidados (naming, docstrings, comentários redundantes)

## Categorias não achadas (resultado válido)

- **SQL injection**: nada encontrado. Todas as queries usam SQLAlchemy 2.0 `select()`
  com bind params. Grep por `text(f"...`, `execute(f"..."`, `f"SELECT"` retornou zero.
- **Arbitrary code execution**: `eval(`, `exec(`, `pickle.load`, `os.system`,
  `shell=True`, `subprocess` — todos retornaram zero em `.py`.
- **Secrets hardcoded**: nenhuma chave real. `PLACEHOLDER_API_KEY =
  "sk-ant-placeholder-unused-with-infer-false"` é literal marcado, `LOCAL_API_KEY =
  "local"` idem (llama-server ignora). `.env` (não commitado por `.gitignore`)
  contém `ANTHROPIC_API_KEY=` vazio; `.env.example` tem `sk-ant-...` (marcador). Nada
  vazando.
- **Emojis em código Python**: nenhum. Grep por emojis unicode retornou 0.
- **Menção a Claude/AI em código**: apenas o model id `"claude-sonnet-4-6"` (config,
  não referência a Anthropic-AI/Claude assistant).
- **`try: pass` silent failures**: nenhum. Grep por `except.*:\s*(pass|...)` retornou 0.
- **TODO/FIXME/HACK/XXX**: nenhum em `.py`. Limpo.
- **Path traversal via `session_id`**: `session_id` não é concatenado em file paths.
  Apenas usado como user_id do mem0 (que é uma string key, não path) e como PK de
  string(64) no DB. Grep confirmou zero matches.
- **Import de `pickle`**: zero.

## Método usado

1. Leitura completa de: `CLAUDE.md`, `docs/architecture.md`, `docs/tasks.md`,
   `docs/inbox.md`, `results.md`, `results.json`, `pyproject.toml`, `.env`,
   `.env.example`, `.gitignore`.
2. Leitura completa dos módulos Python em `core/`, `core/memory/`, `eval/`, `api/`,
   `alembic/`, `scripts/`, e todos os `tests/*.py` (14 arquivos, 78 testes).
3. Leitura dos prompts: `core/prompts/*.txt`, `eval/prompts/*.txt`.
4. Amostragem de cenários JSON: `seed_01.json`, `full_01.json`, `full_04.json`,
   `extended/seed_01.json` + validação estrutural (5 categorias, 30 perguntas).
5. Grep sistemático por padrões suspeitos (secrets, SQL raw, exec/eval, path traversal,
   emojis, silent-fail, TODO/FIXME).
6. `git log --oneline -30` para ver evolução recente e comparar com estado atual da
   documentação.
