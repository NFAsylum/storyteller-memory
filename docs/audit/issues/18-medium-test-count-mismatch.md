# Brief diz 70 testes; suíte real tem 78

**Severity:** Medium
**Priority:** P2
**Category:** Testing / Doc
**Source:** Brief da auditoria original; `tests/*.py` (14 arquivos)

## Descrição

O brief da auditoria afirma "70 rodam em 12.8s, 100% pass".

Contagem real (grep por `^def test_` em `tests/`):
```
tests/test_world_state.py       :  5
tests/test_mem0_adapter.py      :  6
tests/test_story_loop_v2.py     :  4
tests/test_llm_local.py         :  4
tests/test_harness.py           :  5
tests/test_story_loop.py        :  5
tests/test_llm_client.py        : 10
tests/test_full_scenarios.py    :  3
tests/test_seed_scenarios.py    :  4
tests/test_judges.py            :  4
tests/test_scenario.py          :  6
tests/test_api.py               :  7
tests/test_retrieval_policy.py  :  3
tests/test_reflection.py        : 12
------------------------------- : --
Total                           : 78
```

E `test_seed_scenarios.py`, `test_full_scenarios.py`, `test_judges.py` usam
`@pytest.mark.parametrize`, então o count "coletado" pelo pytest é maior que 78.

## Risco

Não é um bug crítico, mas sinaliza dois problemas:
1. **Documentação/estado do projeto está out-of-date**. As task cards em
   `docs/tasks.md:68`, `:119`, mencionam "31 testes" (S1), "52 testes" (S2). Se
   esses números tivessem sido atualizados sprint a sprint, o total atual estaria
   coerente. Não foram.
2. **A auditoria começa com base falsa**: se o brief está errado em algo
   verificável, quantas outras premissas do brief não batem com a realidade?
   Cadeia de trust degrada.

## Fix sugerido

1. **Atualizar `docs/tasks.md`** com o count real por sprint:
   - Sprint 1 fechado: 31 testes ← existente
   - Sprint 2 fechado: 52 testes ← existente
   - Sprint 3 fechado: adicionar count
   - Sprint 4.1 fechado: adicionar count
   - Sprint 4.2/4.3 (parcial): adicionar count
   - Backend API (novo): adicionar count
   - Estado atual: 78 testes

2. **Automação**: adicionar `scripts/test_count.py`:
   ```python
   """Print current test counts by file. Run: poetry run python scripts/test_count.py"""
   import subprocess
   subprocess.run(["poetry", "run", "pytest", "--collect-only", "-q"])
   ```
   Rodar antes de fechar cada sprint pra alinhar `docs/tasks.md`.

3. **Adicionar assertion no CI** (futuro): se pytest coletar < N (esperado
   mínimo), fail o build. Previne remoção acidental de testes.

## Referências

- `docs/tasks.md:68` diz "31 testes" (Sprint 1); `:119` diz "52 testes" (Sprint 2).
