# `simple_recall_judge` é substring match ingênuo — enfraquece o número-manchete

**Severity:** Critical
**Priority:** P0 (o número-manchete depende dessa métrica)
**Category:** Eval
**Source:** `eval/harness.py:98-106`

## Descrição

O juiz padrão do harness é substring containment normalizado:

```python
def _normalize(text: str) -> str:
    return " ".join(text.lower().split())

def simple_recall_judge(question: Question, response_text: str) -> bool:
    """Deterministic recall check: ground_truth or an accepted variant appears in the reply."""
    haystack = _normalize(response_text)
    needles = [question.ground_truth, *question.acceptable_variants]
    return any(_normalize(n) in haystack for n in needles)
```

`_normalize` faz `lower()` + colapsa whitespace, mas **não** remove pontuação
nem valida word boundaries. Ground truths curtos batem em qualquer palavra que
os contenha como substring.

Ground truths reais nos cenários (grepados em `eval/scenarios/`):
- `"Aria"` (aparece em 3 cenários) → bate em "Ariana", "Mariana", "aria" (parte
  de "ária"), etc.
- `"Vex"` → bate em "Vexado", "Vexação", "vex-me".
- `"Nima"` (seed_02) → bate em "animais", "minha".
- `"Tock"` (seed_03) → bate em "tocke", "estoque".
- `"Vera"` (full_04) → bate em "verão", "verão", "veracidade".
- `"Dax"` → bate em "Dax". OK. (curto, mas único no cenário)

Ground truths compostos:
- `"a prisão de Vex"` — pontuação e case ok; mas o modelo pode responder
  "prisão do Vex" e o judge marca como miss por causa do "de" vs "do".
- `"atrás de um retrato na galeria oeste"` — resposta parafraseada não bate.

## Risco

O número-manchete "0% → 90%" (`results.md:16-21`) é o argumento central do
portfólio. Se o resultado tem contaminação por falsos-positivos:

- Métrica infla artificialmente (recall aparente maior que real).
- Reviewer sofisticado (Anthropic, engenheiro sênior) roda alguns casos e
  descobre — credibilidade destruída.
- No cenário oposto (falso-negativo por paráfrase), o headline subestima o
  ganho real da memória, escondendo mérito.

Evidência de que já ocorre: `results.md:27-30` cita reflection "piorou" recall
em cenários longos. Sem estar seguro de que o judge é robusto, o diagnóstico
"reflection é ruidosa" pode estar mascarando "judge é sensível a paráfrase que
mem0-only produzia mais literalmente".

## Fix sugerido

1. **Word-boundary matching** para needles curtos (< 8 chars):
   ```python
   import re
   def _contains(needle: str, haystack: str) -> bool:
       n = _normalize(needle)
       h = _normalize(haystack)
       if len(n) < 8:
           return re.search(rf"\b{re.escape(n)}\b", h) is not None
       return n in h
   ```

2. **Strip de pontuação** em `_normalize`:
   ```python
   _PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
   def _normalize(text: str) -> str:
       return " ".join(_PUNCT_RE.sub(" ", text.lower()).split())
   ```

3. **Auditoria manual**: escrever `eval/audit_recall.py` que roda o judge sobre
   as 60 respostas atuais (30 seed + 30 extended) e imprime cada verdict com
   `(question, ground_truth, response, verdict)`. Marco revisa e conta manualmente
   quantos são falsos-positivos e falsos-negativos. Documentar taxa em `results.md`.

4. **Backup com LLM-as-judge**: `LlmJudge.judge_recall` já existe (`eval/judges.py:67-74`).
   Rodar em modo shadow — compara veredicto substring vs LLM — reporta divergência.
   Se divergência > 10%, o número-manchete precisa ser reportado com a métrica
   mais conservadora + nota explicativa.

## Referências

- LongMemEval (paper referenciado em `CLAUDE.md:127`): usa LLM-as-judge com
  rubric, não substring — https://arxiv.org/abs/2410.10813
