# FAISS store `./.mem0_data` acumula entre runs — sessões órfãs

**Severity:** Medium
**Priority:** P2
**Category:** Performance / UX
**Source:** `core/memory/mem0_adapter.py:17`, `core/memory/mem0_adapter.py:50-58`, `api/main.py:126-134`

## Descrição

`DEFAULT_STORAGE_PATH = "./.mem0_data"` é um diretório único e compartilhado por
todo mundo:
- Todo `Mem0Adapter` construído sem `storage_path` explícito aponta pra cá.
- O `.gitignore:9` cobre esse diretório (bom — não vaza) mas nunca é limpo.
- Cada `session_id` vira uma partição lógica dentro da MESMA collection FAISS
  (`COLLECTION_NAME = "storyteller"`).

Consequências operacionais:

1. **Sessões "deletadas" via API** — issue 07 mostra que a deleção só limpa mem0
   se o passo 3 do delete rodar. Sessões deletadas por curto-circuit ficam
   órfãs no faiss.
2. **Runs de eval** (`run_all_scenarios.py`, `run_experiments.py`) usam
   `session_id = f"{scenario.id}--{config_name}"` (linha 75). Cada run chama
   `memory.clear()` no início — mas se o processo crasha antes do clear, órfãos
   ficam.
3. **Múltiplos processos concorrentes** — dois processos que abrem
   `Mem0Memory.from_config(path=".mem0_data/faiss")` ao mesmo tempo, se o FAISS
   store tem lock file mas o clear/add competem — comportamento indefinido.
4. **Testes rodam `Mem0Adapter(SESSION_ID)`** — não, os testes usam `_FakeMem0`
   (verificado em test_reflection.py, test_harness.py, test_story_loop_v2.py).
   OK, testes não tocam a store real. Bom.

Espaço em disco: `all-MiniLM-L6-v2` produz 384-dim floats (1.5KB por vetor). Um
run de eval completo cria ~50-100 vetores por scenario × 3 configs × 3 scenarios
= ~1MB. Baixo. Mas sem TTL/limite acumula ao longo de semanas.

## Risco

- **Debugging confuso**: `POST /sessions/{new_id}/turn` retorna contexto de
  sessões antigas de mesmo `session_id` (se `new_id` colidir com uma antiga órfã —
  improvável com uuid4, mas veja issue 21 sobre truncar pra 16 hex).
- **Métrica infla artificialmente**: se rodar `run_all_scenarios` duas vezes sem
  limpeza, a segunda run tem contexto residual (porque `memory.clear()` no início
  só limpa a sessão atual, e reflection do run anterior deixou beats). Reflection
  ajuda no run 2 mas o efeito não é atribuível ao config.

  Ah, espera — issue 12 cobre parte disso. Este issue foca no FAISS store físico,
  não no world_state.

- **Deploy Fly.io** (Sprint 6): FAISS store fica no volume da instância. Sem
  procedimento de cleanup/rotação, o volume enche em semanas de uso.

## Fix sugerido

1. **CLI de cleanup** em `scripts/cleanup_mem0.py`:
   ```python
   """Remove FAISS vectors for sessions not present in the DB.

   Run: poetry run python scripts/cleanup_mem0.py
   """
   ```
   Lê sessions do DB, lista partições do mem0, drop órfãos.

2. **Session-scoped storage paths** (mais robusto): `Mem0Adapter(session_id,
   storage_path=f".mem0_data/{session_id}/")`. Cada sessão em pasta própria; o
   delete filesystem-level fica trivial (rm -rf). Tradeoff: mais dirs pequenos.

3. **Adicionar entry no Makefile / scripts** (`clean-mem0`) que rm -rf o
   diretório inteiro entre eval runs — brute force mas eficaz.

4. **Documentar** em `docs/architecture.md` a semântica da store e como zerar
   entre experimentos.

Recomendação: 3 (curto prazo) + 1 (médio prazo).

## Referências

- FAISS docs: https://github.com/facebookresearch/faiss/wiki
- mem0 storage: https://docs.mem0.ai/components/vector-databases/dbs/faiss
