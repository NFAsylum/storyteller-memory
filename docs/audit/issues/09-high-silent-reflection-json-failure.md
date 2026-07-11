# `LlmReflection` engole falha depois de N retries sem log

**Severity:** High
**Priority:** P1
**Category:** Logic / UX
**Source:** `core/memory/reflection.py:279-330`

## Descrição

```python
def consolidate(self, session_id: str, since_turn: int) -> ReflectionResult:
    turns = sorted(...)
    if not turns:
        return ReflectionResult(...)

    last_turn = int(turns[-1].metadata.get("turn", since_turn + 1))
    prompt = self._build_prompt(session_id, turns)
    extraction, cost = self._extract_with_retry(prompt)
    if extraction is None:
        # Couldn't get valid JSON after retries — persist nothing, still report cost.
        return ReflectionResult(
            beats_created=0, characters_updated=0, relations_updated=0, cost_usd=cost
        )
    ...
```

E `_extract_with_retry`:
```python
def _extract_with_retry(self, prompt: str) -> tuple[ReflectionExtraction | None, float]:
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "Extract the structured facts as JSON now."}
    ]
    cost = 0.0
    for _ in range(self._max_retries + 1):
        response = self._llm.generate(system=prompt, messages=messages)
        cost += response.cost_usd
        try:
            return ReflectionExtraction.model_validate(_parse_json_object(response.content)), cost
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": f"...({exc})..."})
    return None, cost
```

Se o modelo local (Qwen 7B) devolver 3x JSON malformado (comum — `results.md:24-30`
descreve exatamente esse cenário para o 7B), o resultado retornado é um
`ReflectionResult(0, 0, 0, cost)`. **Nenhum log, nenhuma exceção, nenhum sinal
externo.** O caller (`api/main.py:189` ou `story_loop._maybe_reflect`) não sabe
que falhou. Custo real foi gasto (2-3 LLM calls) mas nada aparece no `story_beats`.

Comparação: `AnthropicLlmClient` (llm_anthropic.py:96-102) loga cost/tokens/model
via `logger.info`. Reflection não usa logger nenhum — não há `import logging` no
arquivo. Grep confirmou.

## Risco

Cenários:

1. **UI mostra "Reflection completed. 0 personagens, 0 beats"** e o usuário não
   sabe se (a) não tem info nova pra consolidar (esperado) ou (b) o modelo cuspiu
   lixo 3x (falha silenciosa). Zero feedback debuggável.

2. **Depuração do experimento "reflection piorou recall"** (`results.md:27-30`) —
   se parte das reflections do Sprint 4 falharam silenciosamente, o `story_beats`
   está incompleto. Sem log/telemetria, não dá pra saber quantas rodadas foram
   bem-sucedidas.

3. **Custo cobrado sem persistência**: no backend Anthropic pago, cada retry
   custa $0.01-0.05. 3 tentativas malsucedidas = $0.15 sem produzir nada. Sem
   log, o dono da API key vê saldo drenar sem entender.

4. **Silenciamento contradiz `_DEFAULT_MAX_RETRIES = 2`** — o autor investiu em
   retry porque JSON falha; a próxima linha lógica seria logar quando o retry
   fica sem tentativa.

## Fix sugerido

Adicionar logging estruturado (custo baixo, valor alto):

```python
# no topo do arquivo
import logging
logger = logging.getLogger(__name__)

def _extract_with_retry(self, prompt: str) -> tuple[ReflectionExtraction | None, float]:
    messages = [{"role": "user", "content": "Extract the structured facts as JSON now."}]
    cost = 0.0
    for attempt in range(self._max_retries + 1):
        response = self._llm.generate(system=prompt, messages=messages)
        cost += response.cost_usd
        try:
            return ReflectionExtraction.model_validate(_parse_json_object(response.content)), cost
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "reflection extraction attempt %d of %d failed (%s): %r",
                attempt + 1, self._max_retries + 1, type(exc).__name__, str(exc)[:200],
            )
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": f"...({exc})..."})
    logger.error("reflection extraction exhausted retries after %.4f USD", cost)
    return None, cost
```

Também considerar expor a falha no `ReflectionResult`:

```python
class ReflectionResult(BaseModel):
    beats_created: int = Field(ge=0)
    characters_updated: int = Field(ge=0)
    relations_updated: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    extraction_failed: bool = False  # novo
```

E no endpoint `POST /reflect`, retornar `extraction_failed` no JSON pra UI mostrar
toast "Reflection cuspiu JSON inválido — tenta de novo".

## Referências

- Rule of thumb: silent errors > loud errors > silent success. Este código é
  silent errors.
