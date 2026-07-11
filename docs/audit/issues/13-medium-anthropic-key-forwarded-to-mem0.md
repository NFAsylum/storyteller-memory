# `ANTHROPIC_API_KEY` real é forwardado ao mem0 mesmo com `infer=False`

**Severity:** Medium
**Priority:** P2
**Category:** Security
**Source:** `core/memory/mem0_adapter.py:34-58`, `core/memory/mem0_adapter.py:61-78`

## Descrição

`build_mem0_config` sempre injeta a chave Anthropic no config do mem0:
```python
def build_mem0_config(api_key, storage_path, llm_model, embed_model):
    return {
        "llm": {
            "provider": "anthropic",
            "config": {"model": llm_model, "api_key": api_key},
        },
        ...
    }
```

E `build_mem0_memory` resolve a chave a partir de `env` se não vier explícita:
```python
resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or PLACEHOLDER_API_KEY
```

Comentário no código admite que a chave "nunca é usada" porque as chamadas rodam
com `infer=False`. Mas o objeto config passa pela lib mem0, e mem0 constrói o
cliente Anthropic eagerly na init (comment linha 72-74). O cliente **fica com a
chave em memória** — mesmo que nunca chame a API.

Riscos concretos:
1. **Se mem0 logar seu próprio config** em modo debug (é comum em libs de terceiros
   fazer `logger.debug("config=%s", config)`), a chave sai em stdout/stderr.
2. **Se `Mem0Adapter` for pickled/serializado** (não é hoje, mas cache de sessão
   em Redis é um patch comum futuro), o objeto Anthropic client escapa.
3. **Backend `local`** não precisa da chave real. Mesmo assim, se o usuário tem
   `ANTHROPIC_API_KEY` no `.env` (compatibilidade), ela é carregada e forwardada
   pra mem0 sem propósito.

`.env.example:5` sugere que devs coloquem a chave real quando usam backend
Anthropic. Se rodarem com `LLM_BACKEND=local`, a chave real vai pra mem0 e não
tem necessidade.

## Risco

Baixa probabilidade, impacto moderado:
- Log de terceiros vazando chave.
- Se o servidor for comprometido, quem pega um core dump/heap dump pega a chave
  em RAM sem precisar decrypto.
- Se o dev commitar `.env` por engano (pobre `.gitignore` cobre isso, mas erros
  humanos acontecem), a chave está exposta.

## Fix sugerido

Passar `PLACEHOLDER_API_KEY` para mem0 sempre que o backend não for Anthropic ou
o pipeline usar `infer=False`:

```python
def build_mem0_memory(api_key=None, storage_path=None, ...):
    # mem0 config below always uses infer=False in add()/search(), so the LLM is
    # never called by mem0. Pass a placeholder to avoid forwarding a live key we
    # don't need to leak.
    from mem0 import Memory as Mem0Memory
    resolved_key = PLACEHOLDER_API_KEY  # <-- always
    resolved_path = storage_path or os.environ.get("MEM0_STORAGE_PATH", DEFAULT_STORAGE_PATH)
    config = build_mem0_config(resolved_key, resolved_path, llm_model, embed_model)
    return Mem0Memory.from_config(config)
```

Se algum dia mem0 for chamado com `infer=True` (não é hoje), aí explicitamente
passar a chave real via um arg dedicado — e documentar que essa chave vai pra
lib terceira.

Adicionar teste que confirma:
```python
def test_mem0_config_never_receives_real_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-REAL-KEY-DO-NOT-LEAK")
    called_with = {}
    class _FakeMemory:
        @classmethod
        def from_config(cls, cfg):
            called_with.update(cfg)
            return None
    monkeypatch.setattr("mem0.Memory", _FakeMemory)
    build_mem0_memory()
    assert "REAL-KEY" not in called_with["llm"]["config"]["api_key"]
    assert called_with["llm"]["config"]["api_key"].startswith("sk-ant-placeholder-")
```

## Referências

- OWASP Secrets Management: https://owasp.org/www-community/vulnerabilities/Insufficient_Session-ID_Length (relacionado a exposição desnecessária de credenciais)
