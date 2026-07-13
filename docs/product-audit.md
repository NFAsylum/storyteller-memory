# Product Audit — Storyteller (2026-07-12)

Inventário completo do que separa o estado atual de um **produto usável por usuário real**.

Legenda:
- **S** = Severity: `C`ritical (produto quebrado), `H`igh (funciona mas frustrante), `M`edium (evitável), `L`ow (nice-to-have)
- **P** = Priority: P0 (agora), P1 (próximo), P2 (depois), P3 (backlog)
- **E** = Effort estimado em horas

Total: **~40 issues, ~75-110h pra produto usável.**

---

## 0. BUG CRÍTICO — Memory Inspector aparece vazio pra usuário

### 0.1 [C, P0, 3h] Reflection só dispara a cada 5 turnos, sem UI indicando isso
**Status: backend fixado (T1.1).** `DEFAULT_REFLECT_EVERY` 5→2, `GET /state` expõe `next_reflection_at` + `raw_memory_count`, novo `GET /raw-memories`. Falta a parte de UI (indicador "próxima consolidação", botão user-facing, view das raw memories) — vem nas tasks de frontend.

`core/story_loop.py::DEFAULT_REFLECT_EVERY = 5`. Usuário faz 3 turnos, vê "Personagens (0) / Locais (0) / Relações (0) / Beats (0)" e conclui que a memória não funciona. Tecnicamente correto pela spec, **experience-breaking na prática**.
**Fix:**
- Consolidação inicial no turno 1 ou 2 (populate mínimo pra usuário ver que funciona)
- Indicador visível: "Próxima consolidação em 2 turnos"
- Botão "Consolidar agora" no Memory Inspector (planejei como debug button, não foi implementado como user-facing)
- Fallback: mostrar as raw memories do mem0 (populadas turno-a-turno) como pré-reflection state — "Fatos ainda não consolidados: 3 memórias brutas indexadas"

### 0.2 [C, P0, 1h] Sem indicação do que "Personagens", "Locais", "Relações", "Beats" significam
Usuário abre inspector, vê 4 abas vazias, não sabe o que cada uma representa nem o que precisa fazer pra populá-las.
**Fix:** cada aba vazia mostra uma frase explicativa + link "how memory works" pra explicar o modelo.

---

## 1. Qualidade da narração LLM

### 1.1 [C, P0, 2h] Prompt de continuação narrativa genérico
`core/prompts/story_continuation.txt` provavelmente diz "continue the story". Sem tom, gênero, POV, extensão especificados. Modelo 7B produz prosa passável mas homogênea ("the air grew thick with an otherworldly presence" — clichê de fantasia genérica).
**Fix:** prompt aceita placeholders de gênero (fantasy/scifi/horror/romance), tom (serious/comedic/gothic), POV (first/third/omniscient), extensão target (short 80-150w / medium 200-400w / long 500+w).

### 1.2 [C, P0, 3h] Sem "voice" persistente ao longo da sessão
Turno 5 pode ter tom totalmente diferente de turno 15. Sem memória de estilo.
**Fix:** primeiros 2-3 turnos definem "voice signature" que é injetada em turnos futuros ("write in the same tone, tense, and register as the established narration").

### 1.3 [H, P1, 3h] Reflection do LLM 7B produz JSON ruidoso
Nossa própria medição mostrou reflection **piora** recall no 7B (mem0-only 80% vs mem0+reflection 67%). Fatos extraídos são imprecisos.
**Fix:** (a) modelo maior (Qwen 3.6 35B já disponível) só pra reflection; ou (b) prompt de reflection reforçado com "extract only facts explicitly stated in the turns, not inferences"; ou (c) usuário revisa/edita fatos antes de gravar (ver 5.3).

### 1.4 [H, P1, 2h] Sem few-shot examples nos prompts
Continuation e reflection sem exemplos do que é bom output.
**Fix:** 2-3 exemplos por prompt.

### 1.5 [M, P2, 2h] Judge de recall é substring com word boundary
Passa pra "Vex" mas rejeita "o filho de Vex" (correto semanticamente). Recall verdadeiro precisa entendimento, não match textual.
**Fix:** usar LLM-as-judge com prompt tipo "does the response demonstrate knowledge of the fact, even if paraphrased?" (o judges.py já tem estrutura pra isso, não está sendo usado no recall check).

---

## 2. Controles de intent do usuário

> **Status 2.1-2.6: backend + frontend feitos.** Backend (T2.1-T2.3): `SessionConfig` (genre/pov/tone/intensity/length + protagonist) em `session.config`, `POST /sessions` + `PATCH /config` + `GET /story-starters`, diretivas no prompt. Frontend (Fase 2 wizard): `SetupWizard` (4 passos: story&tone / voice / protagonist / starter grid), `SessionConfigChip` no header do chat (resumo + modal de edição → PATCH), starter preenche o 1º turno via `?starter=`. **Falta só:** verificação visual/screenshots (Marco) e o tuning da prosa (`docs/pending-human-tuning.md`). **`max_tokens` por extensão (2.2): feito.** `LlmClient.generate` aceita `max_tokens` (todas as impls); `StoryLoop` + os endpoints de geração passam `max_tokens_for(config)` (brief 300 / medium 700 / long 1200) — além da diretiva de palavras no prompt.

### 2.1 [C, P0, 5h] Sem picker de gênero
Usuário só tem "brief" text. Não pode dizer "quero horror gótico" via UI. Tem que codificar em prosa.
**Fix:** dropdown/pills no topo da sessão: fantasy / sci-fi / horror / mystery / romance / literary / comedy. Cada gênero mapeia pra modificadores no prompt de continuation.

### 2.2 [C, P0, 3h] Sem controle de extensão de turno
Modelo às vezes escreve 100 palavras, às vezes 400. Sem input.
**Fix:** slider "Turn length: brief / medium / long". Traduz em `max_tokens` + prompt directive.

### 2.3 [C, P0, 3h] Sem controle de POV
Primeira pessoa vs terceira vs onisciente muda tudo. Sem escolha.
**Fix:** radio no setup da sessão. Persiste na sessão.

### 2.4 [H, P1, 2h] Sem controle de tom/intensidade
Pode variar de "casual" pra "brutal e explícito" sem intenção do usuário.
**Fix:** slider "Content intensity: SFW / mature / dark". Mapeia em constraints no prompt.

### 2.5 [H, P1, 3h] Sem "protagonist configurator"
> **Status: backend feito (T2.2).** `SessionConfig.protagonist` (role protagonist/author/narrator + character_name + character_role); a diretiva vai pro prompt (`{protagonist}`). Falta a tela do wizard "You are...".

Usuário nem sabe se é o protagonista, ou se ele é o autor descrevendo protagonista. Sem definição de "who am I in this story".
**Fix:** setup wizard: "You are... the protagonist / the narrator / the author. Your character is named... [name]. Your role: [warrior/detective/writer/...]".

### 2.6 [H, P1, 4h] Sem story-starter templates
> **Status: backend feito (T2.3).** `data/story_starters.json` (~28 aberturas, 4 por gênero) + `GET /story-starters[?genre=]` validado por Pydantic. Falta o grid no wizard.

Usuário abre nova sessão, tela em branco. Não sabe o que digitar.
**Fix:** biblioteca de 20-30 story starters ("Aria enters the demon castle..." / "In a cyberpunk Tokyo, 2087..." / "The letter arrived on a Tuesday..." ) com botão "start with this".

---

## 3. Onboarding / primeiro uso

### 3.1 [C, P0, 4h] Home sem CTA claro
> **Status: feito (T7.1).** Hero na 1ª visita (flag `localStorage`): título + pitch da memória verificável + CTA "Nova história" (wizard) + "Como funciona" (modal explicando mem0→reflection→retrieval) + callout do "Comparar com/sem memória". 2ª visita vai direto pro workspace. ("Start example story" pré-populado fica de follow-up — precisa seed no backend.)
Lista de sessões vazia, botão "Nova sessão". Sem hero, sem exemplo, sem "try demo".
**Fix:** landing dentro do app: "Sua história continua exatamente de onde parou. [Botão: Try example story]". Loading uma sessão pré-populada com o example do README.

### 3.2 [H, P1, 3h] Sem tour do Memory Inspector
Usuário não sabe que o Inspector é o "wow" do produto. Vê 4 abas vazias e clica fora.
**Fix:** overlay de destaque na primeira visita: "This is the Memory Inspector — as you write, characters and locations you mention get automatically catalogued here. Try writing 3-5 turns and watch it fill up." (E claro: bug 0.1 tem que estar fixado primeiro pra afirmação ser verdadeira).

### 3.3 [H, P1, 2h] Sem indicação do "Compare with/without memory" (killer feature)
Botão existe mas não é destacado como o valor central do produto.
**Fix:** call-out visual + tooltip: "Try this to see what your story would sound like without the memory system — this is the whole point of this tool." Botão vira brand feature.

### 3.4 [M, P2, 2h] Empty states secos
"No sessions yet" — cinza. Sem ilustração ou próximo passo.
**Fix:** ilustração + microcopy + botão exemplo.

---

## 4. Feedback e status

### 4.1 [C, P0, 2h] LLM turn latência sem indicador visual
> **Status: backend feito (T1.4).** `POST /sessions/{id}/turn-streamed` (SSE) emite `retrieval_start → retrieval_done → llm_start → llm_done → reflection_check → turn_stored`; erro de LLM emite `error` e não persiste turno parcial. Falta a UI consumir o stream. Token-by-token (`llm_token`) fica de follow-up — exige o `LlmClient` expor streaming (muda o Protocol).

Você digita, clica submit, spinner genérico por 15-30s. Sem "carregando prompt / gerando / consolidando memória".
**Fix:** progressive feedback: "Retrieving relevant memories... Generating narration (usually 15-25s)... Storing turn... Done."

### 4.2 [C, P0, 2h] Sem indicação de quando reflection vai rodar
Ver bug 0.1. Usuário não sabe que reflection é intermitente.
**Fix:** "Next consolidation in 2 turns" no header do inspector.

### 4.3 [H, P1, 2h] Sem histórico de custo
Se rodar com Anthropic, usuário paga por token. Sem cost tracker visível.
**Fix:** chip no header "R$ 0.00 spent this session" (ou tokens locais consumidos).

---

## 5. Memory Inspector — profundidade insuficiente

### 5.1 [H, P1, 4h] Cards de personagens minimalistas
> **Status: feito (T3.1).** Memory Inspector v2: avatar (inicial + cor por hash), traços como badges, `turnos X–Y`, resumo de relações por personagem ("2 enemy · 1 ally"), + botões **editar/apagar** em todos os 4 tipos (consomem o PATCH/DELETE do #11). Falta só: chips de turno clicáveis que rolam o chat (defer — precisa coordenação cross-componente) e verificação visual.

Provavelmente só mostra nome + traits em bullet. Sem foto/avatar/histórico.
**Fix:** cada personagem tem: nome + auto-avatar (initial + color hash), lista de traits com badges, "first appeared: turn X", "last seen: turn Y", turnos onde aparece (chips clicáveis que scrollam a chat pra aquele turno), relações resumidas.

### 5.2 [H, P1, 3h] Sem grafo de relações
> **Status: feito (T3.2), SVG inline (Q1 aprovada).** `RelationsGraph`: layout circular ordenado por `last_seen_turn` desc, raio maior p/ >5 relações, labels rotacionados; arestas com cor por `kind` + espessura por |valência|; hover destaca as arestas do nó (dim resto); click no nó → scroll do chat pro 1º turno do personagem (event bus `scroll-to-turn`, reusado pelo T3.1); legend clicável que filtra por tipo; empty state informativo. Sem reactflow. Falta só verificação visual. (Filtro por range de valência: follow-up leve.)

Relações listadas como texto ("Aria-Vex, antagonista, valence -2"). Deveria ser um grafo visual.
**Fix:** react-flow ou similar, nodes = characters, edges = relations com espessura por valence. Filtra por personagem selecionado.

### 5.3 [C, P0, 5h] Sem edição/deleção de fatos falsos
> **Status: backend feito (T3.3).** `PATCH`/`DELETE /sessions/{id}/state/{characters|locations|relations|story-beats}/{id}` (com 404 cross-session). `/state` agora expõe `id` de todos os 4 tipos. Deletar remove o fato do contexto do próximo turno (retrieval lê o world_state — testado). Falta: botões edit/delete nos cards (frontend) e o soft-flag `user_corrected` no mem0 (as memórias brutas são um canal separado; a exclusão do fato estruturado já cobre o "próximo turno não menciona").

Reflection do 7B alucina. Usuário não pode corrigir. Fato falso persiste na memória.
**Fix:** cada character/location/relation/beat tem botão "edit" (change fields) e "delete" (remove from world state). Botão "flag as incorrect" opcional pra dataset de melhoria futura.

### 5.4 [M, P2, 3h] Story beats como wall of text
Reflection gera resumos concatenados sem estrutura visual.
**Fix:** timeline vertical de beats (turn range → resumo), agrupado por batch de reflection, expandable.

### 5.5 [M, P2, 3h] Sem search/filter no inspector
50 personagens = parede de scroll. Sem busca.
**Fix:** search bar no topo de cada aba, filter por "recently active", "mentioned in last 5 turns", etc.

---

## 6. Chat UX

### 6.1 [H, P1, 3h] Sem edição/regeneração de turno
> **Status: backend feito (T4.1).** `PATCH /sessions/{id}/turns/{n}` (edita input + re-narra reusando o contexto original) e `POST .../regenerate` (mesma entrada, nova amostra). Atualizam o world_state DB + a memória mem0 do turno. Falta os botões no chat (frontend).
Se o LLM produziu algo ruim, usuário não pode editar sua ação nem regenerar a resposta.
**Fix:** botão "edit" no user turn (com aviso "isso vai invalidar turnos posteriores"), botão "regenerate" no narrator turn (usa retrieval bundle idêntico + nova amostra do LLM).

### 6.2 [H, P1, 3h] Sem "undo" turn
> **Status: backend feito (T4.1).** `DELETE /sessions/{id}/turns/{n}` remove o turno do DB + a memória mem0 dele; se era o head, `last_turn` recua. Falta o botão undo (frontend).
Digita algo, arrepende, sem forma de desfazer.
**Fix:** last turn tem botão "undo" que remove do mem0 + world_state + chat.

### 6.3 [M, P2, 2h] Sem markdown/rich text no chat
Se usuário quer *itálico* ou negrito na sua descrição, não tem como.
**Fix:** input aceita markdown básico + preview.

### 6.4 [M, P2, 2h] Sem timestamps visíveis
> **Status: feito (T4.2).** Cada turno mostra timestamp relativo ("5 min atrás", "ontem"); actor distinto (input do usuário à direita com accent, narração à esquerda neutra); turno atual com highlight sutil; toggle de auto-scroll no header. Também: botões edit/regenerate/undo/fork por turno (frontend do 6.1/6.2) + Export dropdown (7.1) + Fork (7.3). Falta só verificação visual.

Turno de 3 dias atrás vs 3 min atrás parece igual.
**Fix:** relative timestamps ("5 minutes ago", "yesterday", "3 days ago") em cada mensagem.

---

## 7. Persistência e ciclo de vida

### 7.1 [C, P0, 4h] Sem export da história
> **Status: backend feito (T5.1).** `GET /sessions/{id}/export?format=markdown|txt|json` (attachment). markdown=chat com headings; txt=só narração; json=dump completo (turns+world_state+config). Falta o botão de download (frontend). PDF/epub ficam de follow-up.
Usuário escreveu 50 turnos, quer publicar/compartilhar. Sem export pra .md/.txt/.pdf/.epub.
**Fix:** botão "Export": Markdown (chat format), plain text (só narração formatada como conto), PDF (chapter book format), epub (opcional).

### 7.2 [H, P1, 3h] Session persistence via cookie único
Se usuário limpa cookies ou muda de browser, perde acesso mesmo com dados no servidor.
**Fix:** login mínimo (Google/email) — session ID mapeado a account, não só cookie.

### 7.3 [H, P1, 2h] Sem duplicate/fork de session
> **Status: backend feito (T5.2).** `POST /sessions/{id}/fork?from_turn=N` cria cópia independente até o turno N (turns + world_state com remapeamento de ids de personagem + memórias mem0). Nome `"<orig> — fork"`. Falta o botão (frontend).
Se usuário quer explorar "what if" a partir do turno 20, tem que criar do zero.
**Fix:** botão "Fork from this turn" cria nova session com estado até esse ponto.

### 7.4 [M, P2, 2h] Sem soft delete
Delete session apaga imediatamente. Sem lixeira.
**Fix:** 30-day trash.

---

## 8. Erros e recuperação

### 8.1 [C, P0, 3h] llama-server timeout crash session
Timeout de 30s+ mata request, chat mostra "Failed to fetch", turno perdido.
**Fix:** retry automático (2 tentativas) + toast + preserva user input pra reenvio.

### 8.2 [H, P1, 2h] Reflection falha silenciosa
Se LlmReflection não consegue parsear JSON após retries, engole erro. Custo pago, nada gravado.
**Fix:** toast "Consolidação falhou — tentar novamente?" + botão retry.

### 8.3 [M, P2, 2h] Sem detecção de "LLM está lento"
Se resposta demora >60s, usuário fica olhando spinner. Sem cancel/timeout claro.
**Fix:** progressive backoff — 30s "still working...", 60s "slower than usual, cancel?", 120s automatic cancel.

---

## 9. Responsividade e tema (adicionado pós-feedback)

### 9.1 [C, P0, 5h] Layout não responsivo
> **Status: layout feito (T6.1); testes de viewport = flag de browser.** `Workspace` responsivo: 3 colunas plenas em `xl+`; **sidebar vira drawer com overlay abaixo de `lg`**; **inspector vira drawer abaixo de `xl`**; top bar mobile com botões de menu/memória; chat sempre a coluna primária; `overflow-hidden` evita scroll horizontal. **Pendente (precisa browser):** Playwright viewport tests em 5 tamanhos + screenshots em `docs/screenshots/responsive/` — Marco roda (sem browser aqui; não instalo Playwright sem OK). Desvio: usei **drawers** em vez de tabs no mobile (padrão mais limpo, mesmo objetivo).
Você reportou 100% height / 40% width tela full HD renderiza mal. Layout de 3 colunas assume desktop full width.
**Fix:**
- Breakpoints em Tailwind: `md` (768px) mostra 2 colunas (sidebar + chat, inspector vira drawer), `lg` (1024px) mostra 3 colunas
- Chat central com min-width sensato (400px), inspector à direita colapsável em telas <1280px
- Sidebar de sessions colapsável em telas <900px
- Test em widths: 400px (mobile portrait), 768px (tablet), 1024px, 1440px, 1920px, ultrawide

### 9.2 [C, P0, 3h] Sem theme toggle
> **Status: feito (T6.2).** Toggle sol/lua no header da sidebar; classe `.dark` no `<html>`; detecta `prefers-color-scheme` na 1ª visita e persiste em `localStorage`; script anti-FOUC no layout (sem flash). shadcn já traz as CSS vars de light/dark.
Reportado. Só um tema (provavelmente Slate default do shadcn) e fixo.
**Fix:**
- Toggle dark/light no header
- Detectar `prefers-color-scheme` do sistema no primeiro load
- Persistir em localStorage
- shadcn/ui já suporta variables CSS pra tema — trabalho é configurar + toggle UI

### 9.3 [H, P1, 3h] Componentes não testados em mobile
Vitest só testa render feliz. Nenhum teste de layout mobile ou touch interaction.
**Fix:** adicionar Playwright viewport tests em 3 resoluções (mobile portrait, tablet landscape, desktop). Se não passar, ajustar.

### 9.4 [M, P2, 2h] Fonte pequena em telas grandes
Usuário 4K vê fonte de 14px que fica minúscula.
**Fix:** typography scale relativa (rem) + zoom level control no settings.

---

## 10. Documentação / help

### 10.1 [H, P1, 4h] Nada in-product explica como memória funciona
Usuário abre memory inspector, vê 4 abas vazias, não sabe o que rolar acontece por trás.
**Fix:** modal "How memory works" mostrando: (1) cada turno salvo em mem0 vetor, (2) a cada N turnos LLM extrai fatos, (3) próximo turno recebe context de tudo relevante. Com diagrama.

### 10.2 [M, P2, 2h] Sem tutorial de "como escrever bem"
Usuário digita "Aria vai" e narração fica genérica. Sem guidance sobre inputs que produzem bons outputs.
**Fix:** "Tips for good input" página: describe scene → describe action → let narrator respond. Exemplos bom vs ruim.

### 10.3 [M, P2, 3h] README foca em research angle
`0% → 90% recall` é técnico. Usuário final não sabe se é pra ele.
**Fix:** adicionar seção "Are you a writer / GM / roleplayer?" no topo do README com use case flow.

---

## 11. Deploy pra usuários reais

### 11.1 [C, P0, 6h] LLM local não acessível de deploy remoto
`192.168.3.92` só existe na tua rede. Deploy Fly.io não vê llama-server. Anthropic backend precisa estar completo.
**Fix:** implementar `AnthropicLlmClient.generate()` com Anthropic SDK (provavelmente meio-caminho, ~4h completar), suporte Anthropic reflection também.

### 11.2 [C, P0, 4h] Sem multi-user isolation
Session store não tem user_id. Todas sessões compartilhadas.
**Fix:** login mínimo + user_id em cada tabela + filter em todas as queries.

### 11.3 [H, P1, 3h] Sem quotas
Usuário pode gerar 1000 turnos, gastando LLM cost sem limite.
**Fix:** quota por conta (ex: 100 turnos/dia grátis, upgrade path).

### 11.4 [H, P1, 3h] Sem privacy controls
Session pode conter conteúdo pessoal/sensível. Sem "delete all my data".
**Fix:** GDPR-compliance mínimo — botão "export all my data" e "delete everything".

### 11.5 [M, P2, 4h] Sem observability
Sem logs estruturados, sem métricas, sem alertas.
**Fix:** structured logging + basic metrics dashboard.

---

## Sumário

| Categoria | Issues | Effort |
|---|---:|---:|
| Bug crítico (reflection UX) | 2 | ~4h |
| LLM narração quality | 5 | ~12h |
| User intent controls | 6 | ~20h |
| Onboarding | 4 | ~11h |
| Feedback/status | 3 | ~6h |
| Memory Inspector | 5 | ~18h |
| Chat UX | 4 | ~10h |
| Persistência | 4 | ~11h |
| Erros | 3 | ~7h |
| Responsividade/tema | 4 | ~13h |
| Documentação | 3 | ~9h |
| Deploy multi-user | 5 | ~20h |
| **Total** | **48** | **~141h** |

**Realista:** 80-95h se cortar backlog (P2/P3) e priorizar P0/P1.

---

## Trilhas

**Trilha "usável single-user local" (~45h):**
Bug 0.1 + 0.2, 1.1, 2.1-2.3, 3.1, 4.1-4.2, 5.3, 6.1, 7.1, 8.1, 9.1-9.2, 10.1, 11.1.
Vira produto que **você** consegue usar seriamente pra RPG ou escrita colaborativa.

**Trilha "usável multi-user hospedado" (~95h):**
Trilha 1 + fixes P1 críticos (1.2, 2.4-2.6, 3.2-3.3, 5.1, 5.2, 6.2, 11.2, 11.3, 11.4) + Anthropic backend real.
Vira SaaS pequeno — RPG solo tool + writing assistant.

**Trilha "excelência" (~140h):**
Tudo, incluindo observability e privacy compliance.

Decisão do humano.

---

## Comparação com Balance

Storyteller tem MAIS gaps que Balance porque:
- Balance ao menos tem multi-objective picker (algum controle do usuário)
- Balance tem timeline visual scrubber (algum feedback)
- Balance tem 3 domínios prontos (algum escopo)
- Storyteller é chat + memory inspector nu, sem controles nem presets

O bug 0.1 (reflection a cada 5) sozinho **provavelmente é o motivo do teu descontentamento** — o Memory Inspector é o "wow" do produto e ele parece quebrado com 3 turnos.
