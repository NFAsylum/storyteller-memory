# `_normalize` sem strip de pontuação — "Aria." não bate "Aria"

**Severity:** Low
**Priority:** P3
**Category:** Eval
**Source:** `eval/harness.py:98-99`

## Descrição

```python
def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
```

`text.lower().split()` deixa pontuação intacta. Casos falha:
- Ground truth `"Aria"` procurado em resposta `"Aria."` (com ponto final):
  `"aria" in "aria."` — hit por acaso (substring).
- Ground truth `"Aria."` procurado em resposta `"Aria"` (sem ponto): `"aria." in "aria"` — miss.
- Ground truth `"a prisão de Vex"` procurado em `"a prisão de Vex,"` — hit (substring OK).

Interage com issue 03 (substring matching mais amplo). Aqui é o normalizador
específico.

## Risco

- Falso positivos ocasionais quando resposta tem pontuação e ground truth não
  (raro nos scenarios atuais porque ground_truth é sempre curto e sem período).
- Falso negativos raros mas graves quando `ground_truth` tem virgula/hífen
  intencional (nenhum caso hoje, mas p.ex. "conselheiro-mor Vex" quebra fácil).
- Interação com `acceptable_variants`: `["a cavaleira Aria"]` funciona; `["Aria,
  a cavaleira"]` (com vírgula) só bate se resposta tiver vírgula no mesmo lugar.

## Fix sugerido

Adicionar strip de pontuação:
```python
import re
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

def _normalize(text: str) -> str:
    stripped = _PUNCT_RE.sub(" ", text.lower())
    return " ".join(stripped.split())
```

Adicionar testes específicos:
```python
@pytest.mark.parametrize("gt,resp,expected", [
    ("Aria", "Foi a cavaleira Aria.", True),   # trailing period
    ("Aria,", "Foi Aria", True),                # gt has comma
    ("a prisão de Vex", "É a prisão de Vex!", True),
    ("prisão", "prisão-perpétua", True),        # embedded — see issue 03
])
def test_simple_recall_judge_handles_punctuation(gt, resp, expected):
    q = Question(id="q", asked_after_turn=1, category="recall_factual",
                 question="?", ground_truth=gt, acceptable_variants=[])
    assert simple_recall_judge(q, resp) is expected
```

## Referências

- Combinar com fix de issue 03 (word boundary + strip de pontuação = single-pass).
