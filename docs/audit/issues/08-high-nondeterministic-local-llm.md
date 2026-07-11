# `LocalLlmClient` não fixa `temperature` nem `seed` — medições variam entre runs

**Severity:** High
**Priority:** P1 (impacta reprodutibilidade do número-manchete)
**Category:** Eval / Logic
**Source:** `core/llm_local.py:45-73`, `core/llm_anthropic.py:78-103`

## Descrição

O `LocalLlmClient.generate` monta o request sem `temperature`, `top_p`, ou `seed`:

```python
completion = self._client.chat.completions.create(
    model=self.model,
    max_tokens=self.max_tokens,
    messages=chat_messages,
)
```

`AnthropicLlmClient.generate` idem:
```python
kwargs: dict[str, Any] = {
    "model": self.model,
    "max_tokens": self.max_tokens,
    "messages": messages,
}
```

Defaults reais dos backends:
- llama-server (Qwen2.5-Coder-7B via llama.cpp): `temperature=0.8`, `top_p=0.95`,
  seed aleatória. Cada geração é diferente.
- Anthropic API: `temperature=1.0` default. Cada geração é diferente.

Como o `simple_recall_judge` (`eval/harness.py:102`) faz containment sobre a
resposta, uma resposta ligeiramente diferente pode não conter mais o
`ground_truth`, e o mesmo config passa de 27 pra 25 corretos entre runs.

## Risco

1. **Número-manchete não reprodutível.** `results.md:6-9` afirma "27 of 30 (90%)"
   mas outro rodar pode dar 24, 26, 29. Reviewer que roda pra confirmar vê valor
   diferente e questiona a credibilidade da medição.

2. **Diagnóstico enganoso sobre reflection.** `results.md:24-30` conclui
   "reflection piorou -13pp em cenários longos" — mas se a diferença entre configs
   está dentro do ruído de temperature, o "piorou" pode ser artefato. Sem
   determinismo, não dá pra separar sinal (efeito real de reflection) de ruído
   (variação sampling).

3. **Experiments do Sprint 4 (variantes)** — 4 variantes rodadas 1x cada. Sem
   temperatura zero, o "vencedor" é o que teve mais sorte, não o mais recall.
   `docs/experiments.md` documenta um número mas roda 2 vezes daria vencedor
   diferente.

4. **Judges LLM** (`eval/judges.py:_parse_recall`) recebem respostas variadas
   também — YES em uma run, PARTIAL em outra.

## Fix sugerido

1. **Fixar `temperature=0` e `top_p=1` em ambos backends** para runs de eval:
   ```python
   # llm_local.py
   completion = self._client.chat.completions.create(
       model=self.model,
       max_tokens=self.max_tokens,
       messages=chat_messages,
       temperature=0.0,
       top_p=1.0,
       seed=42,  # llama-server supports this when built with --seed support
   )

   # llm_anthropic.py
   kwargs["temperature"] = 0.0
   ```

2. **Expor override**: `LocalLlmClient(temperature=..., seed=...)` — default 0.0
   e 42 pra eval; UI pode sobrescrever pra 0.8 se quiser variedade narrativa.

3. **Documentar em `results.md`** que os números foram obtidos com `temperature=0`.
   Adicionar seção "Como reproduzir":
   ```
   ## Reprodutibilidade
   Rodado com temperature=0, seed=42. Divergência esperada run-to-run: < 3pp.
   ```

4. **Adicionar teste de determinismo** para o eval:
   ```python
   def test_baseline_recall_is_reproducible():
       result_a = run_config("baseline_mem0_only", "seed")
       result_b = run_config("baseline_mem0_only", "seed")
       assert result_a["correct"] == result_b["correct"]
   ```
   (custa uma run mas prova o point.)

## Referências

- llama.cpp server params: https://github.com/ggerganov/llama.cpp/tree/master/tools/server
- Anthropic API: https://docs.anthropic.com/en/api/messages
