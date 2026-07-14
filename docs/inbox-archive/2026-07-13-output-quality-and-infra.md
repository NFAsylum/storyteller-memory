# INBOX — 2026-07-13 (Storyteller — Output quality + cold-start infra)

Após executar, mova pra `docs/inbox-archive/2026-07-13-output-quality-and-infra.md`.

## Status (2026-07-13)

- ✅ **T-REP.1, T-REP.2, T-REP.3, T-REP.4, T-LANG.1** — mergeados via **PR #22**. Não re-executar.
- ⏸ **T-REP.5** — STANDBY explícito por decisão do Marco (Opção A). Não executar.
- 🆕 **T-INFRA.1** — **task nova adicionada 2026-07-13** (cold-start / lifespan handler). **Executar essa.**

## Contexto original — output quality (histórico, done via PR #22)

Marco reportou em uso real dois sintomas distintos de qualidade de output:

1. **Repetição:** "vez ou outra repete a mesma informação várias vezes".
2. **Drift de idioma:** "vez ou outra a LLM produz texto em inglês (mensagem completa)" mesmo com a história rodando em português.

Fixes cobrindo os dois abaixo, ordenados por ROI.

## Contexto novo — cold-start infra (T-INFRA.1)

Repro'd em 2026-07-13 após restart do backend pós-merge do PR #22: `/health` retornou 500 três tentativas seguidas com `NotImplementedError: Cannot copy out of meta tensor; no data!` do sentence-transformers. Root cause **não é regressão do PR #22** — é padrão de lazy-init em `api/deps.py` que só se manifesta em cold-start.

**Diagnóstico:**

| Peso | Causa | Origem |
|---|---|---|
| 🔴 Alto | `api/deps.py::get_backend()` usa lazy singleton (`_backend: Backend \| None = None`). Primeira request bate em `Depends(get_backend)` → FastAPI resolve dependency **no thread pool** → `build_mem0_memory()` → `SentenceTransformer.__init__` no worker thread. | Projeto (arquitetura) |
| 🔴 Alto | torch 2.13 + transformers 4.57 + sentence-transformers 3.4: `SentenceTransformer` construção fora da main thread hita `Cannot copy out of meta tensor` (bug conhecido, `.to(device)` falha depois do meta init). | Stack (versões incompatíveis) |
| 🟡 Médio | Sem lifespan handler no `api/main.py`. Balance faz corretamente (`api/dependencies.py:43 async def lifespan`) — Storyteller não. | Projeto (arquitetura) |

**Workaround temporário ATIVO em prod (dev):** launcher Python pré-warma `build_backend()` na main thread antes de chamar `uvicorn.run()`. Gambiarra frágil — se container reiniciar sem esse launcher exato, quebra.

**Fix estrutural:** lifespan handler que constrói o backend no startup do app (main thread). ~10 linhas.

### Diagnóstico — repetição

| Peso | Causa | Origem |
|---|---|---|
| 🔴 Alto | `RetrievalPolicy` sempre pega top-5 mem0 sem threshold; sem dedup entre `raw_memories` e `structured_facts` | Projeto |
| 🔴 Alto | Prompt template ativamente pede pra referenciar memórias ("Reference … past events consistently") | Projeto |
| 🟡 Médio | `LocalLlmClient` manda `temperature=0` sem `repeat_penalty`/`frequency_penalty` | Projeto (config) |
| 🟡 Médio | Reflection consolida beats sem dedup semântica (audit #05 já reconhece) | Projeto |
| 🟢 Baixo | Qwen 7B tem variância limitada em prosa longa | Modelo (amplifica, não causa) |

### Diagnóstico — drift de idioma

| Peso | Causa | Origem |
|---|---|---|
| 🔴 Alto | Instrução de idioma está enterrada como bullet no meio das "Craft rules" (`story_continuation.txt`, linha ~19): *"Continue in the same language as the user_input."* Sem ênfase, sem repetição. | Projeto (prompt) |
| 🔴 Alto | Todo o prompt template é em inglês, incluindo os 2 exemplos de concreteness ("The steward's key would not turn..."). Isso ancora o modelo em inglês. | Projeto (prompt) |
| 🟡 Médio | `raw_memories`/`structured_facts` podem vir em inglês (legado pré-PR#21 no reflection). Prompt sofre "code-switching" no contexto e o modelo segue. | Projeto (dados legados) |
| 🟢 Baixo | Qwen 7B tem viés forte pra inglês (treinado em código + inglês predominante). Temperature=0 amplifica: dado prompt com "dose crítica" de inglês, decodifica em inglês. | Modelo |

Ambos os sintomas são amplificados por `temperature=0` sem `repeat_penalty` — o modelo trava em modos determinísticos (repetição léxica ou switch de idioma) que sampling estocástico normalmente quebraria.

## Red lines

- ❌ **`git rebase` proibido.** Use merge.
- ❌ **Sem force push, sem history rewrite.**
- ❌ **Não postar review/comentário/PR no GitHub sem confirmação humana.**
- ❌ **Não mexer em `docker/.env`** (a rule global do Marco vale — GH_TOKEN está lá).

## Ordem sequencial

Todas as tasks têm DoD verificável. Execute na ordem — cada uma tem impacto independente e as anteriores não bloqueiam as posteriores, mas o efeito visual acumula.

### T-REP.1 [5min] Sampling anti-repetição no cliente LLM local

**Onde:** `core/llm_local.py::LocalLlmClient.generate()` — o `client.chat.completions.create(...)` atual manda só `temperature`, `seed`, `max_tokens`, `model`, `messages`. Adicionar sampling params via `extra_body` (llama-server aceita via OpenAI API compat).

**O que adicionar** ao call:

```python
completion = self._client.chat.completions.create(
    model=self.model,
    max_tokens=max_tokens or self.max_tokens,
    messages=chat_messages,
    temperature=self.temperature,
    seed=self.seed,
    frequency_penalty=0.3,
    presence_penalty=0.3,
    extra_body={"repeat_penalty": 1.15},  # llama.cpp-specific, ignored by OpenAI cloud
)
```

**Racional dos valores:**
- `frequency_penalty=0.3`: penaliza tokens já emitidos proporcionalmente à frequência. 0.3 é conservador (0.0 = off, ≥1.0 começa a distorcer prosa).
- `presence_penalty=0.3`: penaliza tokens que apareceram pelo menos 1x. Complementa frequency (frequency = mais frequente pior; presence = qualquer aparição pior).
- `extra_body.repeat_penalty=1.15`: llama.cpp-específico, aplica no nível de token/n-grama. 1.15 é o default "safe" da comunidade llama.cpp (1.0 = off, 1.3+ começa a truncar coerência).

**Determinismo preservado:** `temperature=0` + `seed=42` continua sendo o dominante; os penalties só desviam quando token repetido seria escolhido.

**Não** aplicar em `AnthropicLlmClient` (Anthropic API não aceita esses params; eles já têm anti-repetição built-in).

**DoD:**
- 3 params adicionados em `generate()` com os valores acima
- Docstring atualizada explicando por que (breve)
- Teste em `tests/test_llm_local.py` valida que `chat.completions.create` foi chamado com os 3 params — mock a chamada e faça assert dos kwargs
- Manual test: rode uma sessão nova de 5 turnos com backend local e compare com uma sessão de 5 turnos pré-fix (pode manter git stash do sampling antigo pra comparar). Espere ver menos "porta de carvalho range" tipo eco.
- `pytest tests/test_llm_local.py` verde

### T-REP.2 [10min] Score threshold no mem0.search

**Onde:** `core/memory/retrieval_policy.py::RetrievalPolicy.build_context()`, linha 45:
```python
raw_memories = [m.text for m in self._memory.search(user_input, top_k=self._top_memories)]
```

**Problema:** sempre retorna 5, mesmo se as top-5 têm similaridade cosseno baixa (0.2-0.4). Memórias fracamente relacionadas viram noise que o modelo re-narra.

**Fix:** adicionar filtro por score. mem0 retorna score no `Mem0Adapter.search()` — checar se está exposto. Se não estiver, expor.

**Passos:**
1. Verificar assinatura de `Mem0Adapter.search()` — se retorna `MemoryHit` com `score`, ótimo; se não, adicionar score ao tipo de retorno.
2. Em `RetrievalPolicy`, adicionar constante `DEFAULT_MEMORY_SCORE_THRESHOLD = 0.5` (calibrar depois se preciso).
3. Filtrar: `raw_memories = [m.text for m in self._memory.search(...) if m.score >= self._score_threshold]`.
4. Adicionar `score_threshold` como parâmetro opcional do `__init__` (default `DEFAULT_MEMORY_SCORE_THRESHOLD`).

**DoD:**
- `RetrievalPolicy.__init__` aceita `score_threshold` (default 0.5)
- `build_context()` filtra memórias por score
- Testes em `tests/test_retrieval_policy.py` cobrem: (a) memória com score 0.8 passa; (b) memória com score 0.3 é filtrada; (c) threshold customizado funciona
- Se `Mem0Adapter.search` não expunha score, ajuste testado em `tests/test_mem0_adapter.py`
- `pytest tests/test_retrieval_policy.py tests/test_mem0_adapter.py` verde

**Se travar:** se mem0 não expõe score na API atual (dependendo da versão da lib), documente em `docs/questions-archive/2026-07-13-q-mem0-score.md` e **escale**. Não hardcode um mock.

### T-REP.3 [10min] Dedup entre raw_memories e structured_facts

**Problema:** o mesmo evento pode aparecer em ambos:
- `raw_memories`: turno bruto armazenado no mem0
- `structured_facts`: consolidação do mesmo turno pelo reflection

O prompt injeta os dois, o modelo vê a informação duplicada e re-narra.

**Onde:** `core/memory/retrieval_policy.py::build_context()`, após montar as duas listas.

**Estratégia (simples primeiro):**
```python
# Dedup por overlap textual grosseiro: se um fact é substring/superstring
# de uma raw_memory (ou vice-versa acima de threshold), preserve o fact
# (mais conciso) e dropa a raw.
def _overlap_ratio(a: str, b: str) -> float:
    """Simple word-set Jaccard between two short strings."""
    aw, bw = set(a.lower().split()), set(b.lower().split())
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / len(aw | bw)

DUP_THRESHOLD = 0.6

raw_memories = [
    r for r in raw_memories
    if all(_overlap_ratio(r, f) < DUP_THRESHOLD for f in structured_facts)
]
```

Estratégia melhor (se sobrar tempo): embedding cosine sim, mas custa 1 chamada extra por par. Fica pra follow-up se Jaccard não resolver.

**DoD:**
- Função de dedup implementada em `retrieval_policy.py` (helper `_overlap_ratio`)
- `build_context()` aplica dedup **depois** do score threshold (T-REP.2), **antes** do return
- Teste `test_dedup_overlap_drops_raw_when_matching_fact` em `tests/test_retrieval_policy.py`
- Teste `test_dedup_preserves_orthogonal_raws` — memória não relacionada a nenhum fact não é dropada
- `pytest tests/test_retrieval_policy.py` verde

### T-REP.4 [20min] Reformular prompt template pra desincentivar re-narração

**Onde:** `core/prompts/story_continuation.txt`.

**Diff conceitual:**

Linha atual (Craft rules, ~4ª):
```
- Reference characters, locations, and past events consistently with world_state and retrieved_memories.
```

Substituir por:
```
- Treat world_state and retrieved_memories as CONTEXT (what the narrator knows), not as CONTENT to repeat. Only invoke a past event in the current turn if the user_input requires it, if it directly drives what happens now, or if a character actively remembers it. Otherwise, move the story forward — assume the reader remembers what already happened.
- Consistency check: if a fact appears in world_state or retrieved_memories, do not restate it in the same words. If you must reference it, do so obliquely (a gesture, a shortened callback, an implication) rather than a full recap.
```

Adicionar também aos exemplos de concreteness:
```
- Weak (repetition): "Ivan pushed through the same oak door, hearing the familiar creak — the door he'd first entered two nights ago." Strong (implication): "The door still creaked, though he barely noticed now."
```

**DoD:**
- Prompt template atualizado com o bloco acima
- Adição não excede 20% do tamanho atual do template (ver `wc -l`)
- Manual test: rode a mesma sessão de 5 turnos (com o mesmo `seed=42`), compare com pré-fix. Espere: (a) descrições menos redundantes; (b) callbacks mais implícitos; (c) turnos não repetem exatamente o mesmo detalhe sensorial 2x.
- Não há teste automatizado direto do prompt — é UX/qualidade. Documente o antes/depois com `docs/experiments.md` (adicione seção "F1.6: prompt anti-repetição"). Compare com 3 sessões de baseline.

**Se prompt não convergir após 3 iterações:** escale. Prompt tuning é território do humano por convenção do CLAUDE.md.

### T-LANG.1 [10min] Trava de idioma no prompt template

**Onde:** `core/prompts/story_continuation.txt`.

**Problema:** a instrução atual está enterrada no meio das Craft rules como um bullet:
```
- Continue in the same language as the user_input.
```
Sem ênfase, sem repetição, competindo com 8+ outros bullets. Modelo 7B com `temperature=0` e prompt template inteiro em inglês (incluindo 2 exemplos concretos em inglês) escorrega pra inglês quando o `user_input` é curto ou o contexto retrieved tem inglês legado.

**Fix — 3 partes:**

**(a) Bloco de trava no TOPO do template**, antes de `<style>`:

```
<language_lock>
Write your entire response in the SAME LANGUAGE as <user_input>. This is a hard
constraint. If <user_input> is in Portuguese, respond entirely in Portuguese. If
in English, entirely in English. Never mix languages within a response and never
default to English when the user wrote in another language. Established character
names, place names, and proper nouns stay unchanged; everything else — narration,
dialogue, descriptions, internal thoughts — must be in the user's language.
</language_lock>
```

**(b) Adicionar exemplo em português** aos "Two short examples of the concreteness bar" — hoje ambos são em inglês, ancorando o modelo. Trocar um por PT:

```
- Weak (PT): "O ar ficou pesado, e ela sentiu uma presença estranha."
  Strong (PT): "Os ouvidos dela estalaram, do mesmo jeito que estalavam na estrada da serra, mesmo o quarto estando ao nível do mar."
```

Mantém 1 exemplo em inglês (o do steward's key), adiciona 1 em PT. O modelo vê que ambos os idiomas são válidos e evita ancorar exclusivamente em inglês.

**(c) Repetir a instrução no final** logo antes de `Continue the story now:`:

```
Remember: your response must be entirely in the same language as <user_input>.
Continue the story now:
```

Redundância intencional — o final do prompt tem peso desproporcional na atenção do modelo.

**DoD:**
- Template atualizado com as 3 partes (topo `<language_lock>`, exemplo PT, reminder final)
- Adição não excede 25% do tamanho atual (compare `wc -l` antes/depois)
- Manual test: 3 sessões em português com backend `local` (`seed=42`), 5 turnos cada. Espere: **zero** respostas em inglês. Se aparecer 1+, escale — o prompt não convergiu, humano cuida do tuning.
- Manual test cruzado: 1 sessão em inglês pra garantir que o lock não força PT em input inglês. Espere: response em inglês.
- Compatível com T-REP.4 (mesmo arquivo). Aplique as duas mudanças na mesma edição — não são conflitantes.

**Se não convergir após 3 iterações do prompt:** escale. É território de tuning humano (mesma regra de T-REP.4).

### T-INFRA.1 [15min] Lifespan handler pra warmup do backend na main thread

**Contexto:** o padrão atual (`api/deps.py::get_backend` com lazy singleton `_backend`) constrói mem0 na primeira request → sentence-transformers 3.4 + torch 2.13 quebra fora da main thread (`Cannot copy out of meta tensor`). Balance faz isso corretamente via `api/dependencies.py::lifespan` — replicar o mesmo padrão aqui.

**Onde:** `api/main.py` — adicionar `lifespan` handler + wirar no `FastAPI(...)`.

**Fix — 3 passos:**

**(1) Adicionar lifespan handler no `api/main.py`** (perto do topo, após imports):

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm heavy resources on the main thread at startup — mem0/sentence-transformers has
    known meta-tensor bugs when SentenceTransformer.__init__ runs on a worker thread (which is
    what FastAPI's threadpool would do for a lazy Depends(get_backend))."""
    from api.deps import build_backend
    import api.deps as _deps
    _deps._backend = build_backend()
    yield
```

**(2) Passar o lifespan pro FastAPI**: procurar a linha `app = FastAPI(...)` e adicionar `lifespan=lifespan`:

```python
app = FastAPI(title="Storyteller", lifespan=lifespan)  # ou o title atual
```

**(3) Ajustar o launcher no docker-compose / start command** (se existir warmup gambiarra):
- **REMOVER** o launcher Python que faz `build_backend()` antes de `uvicorn.run()`.
- Voltar pro comando canônico: `uvicorn api.main:app --host 0.0.0.0 --port 8000`.
- Se o start command estiver dentro de docker-compose, `docker/entrypoint.sh`, ou script de bootstrap: procure grep por `build_backend` fora de `api/`.

**DoD:**
- `api/main.py` tem `@asynccontextmanager async def lifespan` que chama `build_backend()` e atribui a `api.deps._backend`.
- `FastAPI(...)` construído com `lifespan=lifespan`.
- Nenhum warmup manual em launcher / start command / entrypoint (grep zero fora de `api/main.py`).
- Manual test: `docker compose restart claude-code-vae` (ou equivalente) → primeiro `curl http://localhost:8001/health` responde **200** com `mem0_ready:true`, **sem 500 intermediário**.
- Teste automatizado NÃO é necessário (é infra de bootstrap, coberto pelo manual test); mas se quiser: `tests/test_api_lifespan.py` que usa `TestClient` como context manager e valida `_backend is not None` após `with TestClient(app) as client:`.
- `pytest tests/` inteiro continua verde.

**Verificação secundária (post-fix):**
- Startup log deve mostrar mem0 sendo construído **antes** de "Uvicorn running on http://0.0.0.0:8000". Se ficar depois, é indicador de que o lifespan não foi wirado.
- Tempo de startup vai aumentar em ~30-60s (é o custo de construir mem0). Comportamento esperado — melhor pagar no startup do que na primeira request.

**Se travar:** se o lifespan não pegar (mem0 continua construindo em worker thread), verifique se `FastAPI(...)` está mesmo com `lifespan=`. Se depois disso ainda houver problema, escale — pode ser bug do próprio FastAPI/uvicorn com startup events em modo específico.

### T-REP.5 [STANDBY — não executar agora] Dedup semântica na reflection

**Status:** decisão tomada em 2026-07-13 — **Opção A (não aplicar agora)**. Aguardando condição de acionamento.

**Contexto:** issue #05 do audit (`docs/audit/issues/05-high-story-beat-duplication-on-rerun.md`) mapeia o bug: `persist_beats` (`core/memory/reflection/persist.py:89`) faz `world.add(StoryBeat(...))` cego, sem checar duplicata. Cliques repetidos em "Force reflection now" (Sprint 5 UI) acumulam beats duplicados em `story_beats`; `top_beats(k=3)` ordenado por `importance DESC` pode servir a mesma info 2-3x pro prompt.

**Por que não agora:** o sintoma reportado ("vez ou outra pode repetir") bate mais com loop determinístico de 7B sem `repeat_penalty` (T-REP.1) do que com acumulação estrutural em `story_beats`. Jaccard word-set (a única opção viável sem migration) tem falso positivo específico em ficção: *"Ivan entra na taverna"* vs *"Ivan volta à taverna"* colapsam. Trade não vale enquanto T-REP.1-4 não foram testados em uso real.

**Condição de acionamento (o que ligar essa task):**

Após T-REP.1-4 mergeados e 3-5 sessões de 8-10 turnos rodadas em uso real, se Marco observar **repetição sistemática** — não esporádica — de qualquer um dos padrões:

1. Narrador reintroduz o mesmo personagem/lugar/fato **em turnos consecutivos** (ex: "Ivan, o guerreiro cansado, entra…" turno 5, "Ivan, o guerreiro cansado…" turno 6, "Ivan, o guerreiro cansado…" turno 7).
2. Memory Inspector (T3.1) mostra beats duplicados visíveis pro usuário.
3. Clique em "Force reflection now" duas vezes cria beats claramente redundantes na inspeção.

Repetição **esporádica** ("vez ou outra") **não** aciona — é sinal de sampling (T-REP.1), não de acumulação (T-REP.5).

**Se acionada, escopo mínimo recomendado** (Opção B do comparativo, não a "completa"):

- Estratégia: Jaccard word-set entre beat novo e beats existentes do session, threshold **0.8** (mais conservador que os 0.7 iniciais — trade off falso positivo em ficção).
- Local: `core/memory/reflection/persist.py::persist_beats()`. Antes do `world.add`, query `SELECT * FROM story_beats WHERE session_id=?`, compare via helper `_overlap_ratio` (mesmo Jaccard de T-REP.3).
- Merge semântico: se overlap ≥ 0.8, mantém beat existente, `importance = max(a, b)`, `turn = max(a.turn, b.turn)`, `tags = a.tags | b.tags`. Nunca perde info estritamente.
- Zero migration. Zero mudança de schema.
- Testes cobrindo: (a) beat idêntico é merged; (b) paráfrase 80% overlap é merged; (c) "volta à taverna após semanas" (overlap ~0.6) é preservado como beat distinto; (d) reflection idempotente após double-click.

**NÃO** implementar embedding-based com migration (Opção C) — over-engineering pro escopo atual do produto.

**Se acionada:** primeiro edite este arquivo removendo "STANDBY" do título, escale mudança de status pro Marco, aguarde confirmação, aí implemente.

---

## Verificação final (após T-INFRA.1)

- [ ] `pytest tests/` inteiro verde
- [ ] Manual test — **cold-start**: parar uvicorn, iniciar via **comando canônico** (`.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000` sem launcher de warmup), primeiro `curl /health` responde 200 com `mem0_ready:true` sem 500 intermediário.
- [ ] Grep zero: `grep -rn "build_backend" .` fora de `api/deps.py` e `api/main.py` (garante que warmup gambiarra foi removido de qualquer lugar).
- [ ] Startup log mostra mem0 construído antes de "Uvicorn running on http://0.0.0.0:8000".

## Depois de tudo verde

1. `git push` da branch
2. Abrir PR: `fix: lifespan handler pra cold-start reliability (T-INFRA.1)`
3. Body do PR: descreve o bug (meta tensor em worker thread), a solução (lifespan warmup), reference ao padrão do Balance (`api/dependencies.py::lifespan`), e menciona a remoção do launcher gambiarra. Inclua o output do manual test (curl /health imediatamente pós-startup respondendo 200).
4. **Aguardar autorização humana** pra:
   - Merge do PR

**Não faça merge sem confirmação.** É mudança em bootstrap de API — se der errado, o serviço não sobe.

## Diretiva sobre escopo

**T-REP.1 a T-REP.4 + T-LANG.1 já foram merged** em PR #22 (2026-07-13). **Não re-executar.**

Executar **apenas T-INFRA.1** nesta rodada. **T-REP.5 continua em standby** por decisão do Marco em 2026-07-13 (Opção A do comparativo pró/con). **Não implemente** T-REP.5 mesmo que dê tempo — ela tem gatilho condicional documentado dentro da própria task.

Se travar em qualquer ponto (mem0 sem score exposto, teste que exige refactor não trivial, prompt não convergindo), **escale imediatamente**. Precedente: preemptive cuts geram under-delivery.

Reporte no próximo prompt:
- SHA dos commits (1 por task idealmente, ou 1 commit atomic se preferir)
- Confirmação de DoD verde de cada task (T-REP.1 a T-REP.4)
- Findings do manual test (antes/depois, mesmo qualitativo)
