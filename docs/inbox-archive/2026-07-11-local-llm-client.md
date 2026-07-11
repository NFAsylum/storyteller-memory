# INBOX — 2026-07-11 (Storyteller)

Instrução única do orquestrador humano+claude-host. Após executar, mova este arquivo pra `docs/inbox-archive/YYYY-MM-DD-hhmm.md` ou apague — não deixe estagnado.

## Task: implementar `LocalLlmClient` (backend LLM local via llama-server)

**Contexto:** já testamos a conexão do container com o servidor local. O endpoint responde OpenAI-compatible. Configuração está em `.env` (já criado). Modelo carregado é Qwen2.5-Coder-7B-Instruct Q4_K_M, ~102 tokens/s de geração com GPU offload.

### Ação

1. **Dependência:** adicionar SDK OpenAI ao projeto:
   ```bash
   poetry add openai
   ```

2. **Novo arquivo `core/llm_local.py`:**
   - Classe `LocalLlmClient` implementando o `LlmClient` Protocol
   - Usa `openai.OpenAI(base_url=os.getenv("LOCAL_LLM_URL"), api_key="local")`
   - O `api_key="local"` literalmente — llama-server ignora, mas o SDK exige o campo
   - Retorna `LlmResponse` com `content`, `stop_reason`, `usage`, `cost_usd=0.0`
   - Não implementar retry exponencial complexo (llama-server local não tem 429). Timeout 120s (modelo local é mais lento que Anthropic).

3. **Factory em `core/llm_client.py`:**
   ```python
   LLM_BACKEND=fake     -> FakeLlmClient
   LLM_BACKEND=anthropic -> AnthropicLlmClient
   LLM_BACKEND=local    -> LocalLlmClient
   ```
   Levanta `ValueError` claro se `LLM_BACKEND` inválido ou variáveis do backend selecionado faltando.

4. **Smoke test `scripts/smoke_local.py`:**
   - Verifica que `LOCAL_LLM_URL` responde (chama `/v1/models`)
   - Faz uma chamada de completion trivial ("Reply with OK")
   - Imprime latência total, tokens gerados, tps observado
   - Roda com `poetry run python scripts/smoke_local.py`

5. **Testes automatizados:**
   - `tests/test_llm_local.py` com 3 casos (mock do OpenAI SDK, não hit real):
     - Retorna LlmResponse válido
     - Factory retorna LocalLlmClient quando LLM_BACKEND=local
     - Falha claro se LOCAL_LLM_URL não setado

### Verificação (DoD)

- [ ] `poetry install` sem erro depois do `poetry add openai`
- [ ] `LLM_BACKEND=local poetry run python scripts/smoke_local.py` responde em <10s com "OK"
- [ ] `pytest tests/test_llm_local.py` verde (mock)
- [ ] `pytest` inteiro do projeto continua verde
- [ ] Factory testada com os 3 valores válidos + 1 inválido

### Impacto no plano

Isso desbloqueia Sprint 3 (real LLM + primeira medição) usando LLM local em vez de Anthropic paga. **Sem custo por token, sem rate limit.** Métrica "baseline vs augmented" continua válida — o que importa é ser o mesmo modelo em ambas as configs.

Depois de aplicado, pode prosseguir pra Sprint 3 com `LLM_BACKEND=local` no `.env` (já está setado).

### Notas técnicas

- llama-server aceita qualquer valor no campo `model` do request — usa o modelo carregado. Não valida.
- Se receber erro de context overflow em prompts longos, avisar humano — talvez precise raise do `-c` no llama-server (hoje 16k, treinado pra 32k).
- Cost logging: `cost_usd=0.0` sempre pra impls local. Manter o campo pra compatibilidade da interface.
