# INBOX — 2026-07-11 (Storyteller)

Após executar, mova esta task pra `docs/inbox-archive/YYYY-MM-DD-hhmm.md` ou apague.

## Task: S3.5 follow-up — eval discriminante (número-manchete de portfólio)

**Contexto:** você rodou S3.5 e escalou corretamente (delta +3pp com gate <5pp). O `results.md` identifica saturação do baseline (top-5 memories cobrindo todos os fatos em cenários de 5 turnos). Análise perfeita — o problema é o eval design, não a reflection.

**Objetivo:** produzir o número que vai no README/portfólio: **"Sem memória: X%. Com memória: 90%+"**. É esse delta que vende, não "mem0-only vs mem0+reflection" que satura.

### Ação

**Opção 3 (obrigatória) — baseline "sem memória":**

1. Adicionar nova `HarnessConfig` chamada `no_memory`:
   - `use_retrieval=False`
   - `use_reflection=False`
   - `mem0.add()` **não** é chamado durante os turnos (não armazena nada)
   - Prompt de continuação recebe **apenas o input do usuário do turno atual** — nenhum contexto de turnos anteriores injetado
2. Rodar `no_memory` contra os 3 cenários seed atuais
3. Adicionar ao `results.md` no formato:
   ```
   sprint 3 no_memory (LLM puro): N of 30 recall (X%)
   sprint 3 mem0_only:             27 of 30 recall (90%)  [já existe]
   sprint 3 mem0 + reflection:     28 of 30 recall (93%)  [já existe]
   ```
4. Escrever 1 parágrafo em `results.md` conectando:
   - Número-manchete: "sem memória, o LLM acerta X%; com o sistema de memória, sobe pra 90-93%"
   - Nota metodológica: cenários curtos (5 turnos) saturam quando qualquer memória é injetada, por isso o delta mem0 vs mem0+reflection é pequeno; a diferença brilha entre "sem nada" vs "com sistema"

**Opção 1 (bônus, ~1h se der tempo) — cenários mais longos:**

5. Estender `eval/scenarios/seed_01/02/03.json` pra 15-20 cenas cada (mantendo 10 perguntas por cenário, 30 total)
6. Rerun das 3 configs (`no_memory`, `mem0_only`, `mem0_plus_reflection`) contra cenários estendidos
7. Adicionar seção "cenários estendidos" em `results.md` — reflection provavelmente fica discriminante em histórico longo (top-5 raw memories não cobre tudo, world_state consolidado passa a importar)

### Verificação (DoD)

- [ ] `HarnessConfig` `no_memory` implementada e testada com FakeLlm (1 teste)
- [ ] `results.md` tem 3 linhas de recall + parágrafo interpretativo
- [ ] Número `no_memory` está < 60% (senão o eval ainda não é discriminante o suficiente — reportar e discutir)
- [ ] Opção 1 (se feita): 3 cenários com 15+ cenas cada, resultados numa seção separada
- [ ] `pytest` inteiro continua verde

### Depois

Sprint 3 fecha. Segue pro Sprint 4 (harness expandido, judges subjetivos, iteração de prompt/retrieval) usando o eval discriminante que acabou de construir.

### Notas

- Se `no_memory` sair alto (>70%), tem coisa vazando contexto pro LLM — investigar. Idealmente < 40% pra ter um delta forte.
- Custo esperado: $0 (backend local).
- Tempo: ~30min Opção 3, +1h Opção 1 se fizer.
