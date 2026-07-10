# Storyteller — LLM com Memória de Longo Prazo

## Missão

Construir MVP de gerador de histórias que demonstra memória de longo prazo **verificável**. Diferencial: harness de avaliação quantitativa que prova recall cross-session, consistência de personagens, evolução de world state. Não é chat com vector store.

Projeto tocado como portfólio de TCC. Prazo ~5-6 semanas @ 20h/sem. Você (Claude) é o executor principal; o dev humano (marco) intervém em decisões de escopo e prompt tuning.

## Stack fixado

- Python 3.11 + Poetry
- **SQLite** (world state estruturado, dev) + `mem0ai` (retrieval)
- FastAPI (backend) + Streamlit (frontend MVP)
- Anthropic SDK, modelo `claude-sonnet-4-6`
- pytest para testes
- Deploy: Fly.io + Fly Postgres

**Migração futura (Sprint 5, antes do polish final):** SQLite → Postgres 16. Feita via `DATABASE_URL` + Alembic (schemas devem ser portáveis desde o início: sem tipos Postgres-only como JSONB/ARRAY — use `JSON` genérico). O motivo de SQLite no dev é evitar overhead de infra pro Claude no container (sem docker-in-docker).

Não trocar sem justificativa forte + confirmação do humano.

## Layout do repo

```
storyteller/
├── CLAUDE.md                    # este arquivo
├── docs/
│   ├── architecture.md          # módulos e interfaces
│   ├── tasks.md                 # sprints com definition of done
│   ├── prompts.md               # templates LLM iteráveis
│   └── experiments.md           # log de A/B, criado no Sprint 3
├── bootstrap.sh                 # cria estrutura Python
├── pyproject.toml
├── docker-compose.yml           # Postgres local
├── core/
│   ├── llm_client.py
│   ├── story_loop.py
│   ├── memory/
│   │   ├── mem0_adapter.py
│   │   ├── world_state.py
│   │   ├── reflection.py
│   │   └── retrieval_policy.py
│   └── prompts/                 # arquivos .txt versionáveis
├── eval/
│   ├── harness.py
│   ├── scenarios/               # JSON de cenários de teste
│   └── judges.py
├── api/                         # FastAPI
├── ui/                          # Streamlit
├── tests/
└── deploy/                      # Dockerfile, fly.toml
```

## Fluxo de trabalho por task

1. Ler `docs/tasks.md`, pegar próxima task pendente (checkbox `[ ]`)
2. Criar branch: `git checkout -b dev-marco-s<N>-<task-id>` (ex: `dev-marco-s1-1.3`)
3. Implementar
4. Rodar: `pytest tests/` — todos verdes antes de continuar
5. Verificar Definition of Done da task; **cada critério tem que ser verificável programaticamente**
6. Commit: `git commit -m "S1.3: story loop v1 with mem0 storage"` (sem menção a AI, sem emoji)
7. Marcar task como feita em `docs/tasks.md` (`[x]`)
8. Se DoD não é 100% verificável ou algo ficou pela metade: **NÃO marcar feita, escalar pro humano**

## Guardrails (rígidos)

- Nunca commit em `main` — sempre branch `dev-marco-*`
- Nunca `--no-verify` em hooks
- Nunca `git rebase` — use merge
- Nunca skip de teste sem justificativa em comentário e sem tag `@pytest.mark.skip(reason=...)`
- Se estourar 30% da estimativa de uma task, **para e pergunta ao humano**
- Se DoD é vaga demais pra ser auto-verificável, **para e pergunta**
- Configurar git author antes do primeiro commit:
  ```bash
  git config user.name "NFAsylum"
  git config user.email "marcooinotna13@outlook.com"
  ```
- Nunca usar `--dangerously-skip-permissions` fora do container (já vem default via alias do Dockerfile — não invocar de novo)
- Nunca postar review/comentário no GitHub sem confirmação humana

## Quando escalar pro humano

- Decisão de escopo (adicionar/cortar feature não prevista em `docs/tasks.md`)
- Prompt LLM não converge após 3 iterações — humano cuida do tuning
- Harness mostra regressão inexplicável (>5pp pra baixo)
- Estimativa estourada em >30%
- Bug em dependência externa que exige workaround não-trivial
- API key da Anthropic faltando ou expirada

## Modelo mental do produto

**Contador de histórias** = LLM que continua narrativa com base em input do usuário.

**Memória de longo prazo** = o sistema lembra de forma verificável:
- Eventos de sessões passadas (recall factual)
- Traços de personagens (consistência)
- Evolução de relacionamentos
- Estado atual do mundo (locais, itens, tensões políticas)
- E esquece seletivamente detalhes irrelevantes (não é log infinito indexado)

**Diferencial de portfólio:** harness quantitativo, ex. "58% recall em 30 perguntas ao longo de 5 sessões vs baseline 22% sem memória". Sem números medidos, é toy demo — não passa.

## Convenções

- Português em docs, comentários pro humano, commits em português OK
- Inglês em código, docstrings, e prompts LLM
- Não usar termos vagos ("objetos", "processa dados") — nomear tipos/classes específicos
- Reports/logs usam formato "N of M" pra counts

## Referências rápidas

- `docs/architecture.md` — como os módulos conectam
- `docs/tasks.md` — o que fazer agora
- `docs/prompts.md` — templates iniciais dos prompts LLM
- mem0 quickstart: https://docs.mem0.ai/platform/quickstart
- Anthropic Python SDK: https://github.com/anthropics/anthropic-sdk-python
- LongMemEval (referência para harness): https://arxiv.org/abs/2410.10813
