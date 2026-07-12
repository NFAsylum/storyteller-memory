# `FakeLlmClient` narra sempre em português — não respeita `user_input`

**Severity:** Low
**Priority:** P3
**Category:** UX / Testing
**Source:** `core/llm_fakes.py:15-21`

## Descrição

Os 5 templates do FakeLlmClient são todos em português:
```python
_TEMPLATES: tuple[str, ...] = (
    "As tochas tremeluzem no salão. {echo} O ar pesa com o que ainda não foi dito.",
    "A cena se desenrola em silêncio. {echo} Ao longe, um sino soa uma única vez.",
    "Passos ecoam pela pedra fria. {echo} Uma sombra hesita à beira da luz.",
    "O vento cruza as ameias. {echo} Algo mudou, e todos sentem, sem saber nomear.",
    "A corte prende a respiração. {echo} O momento se estende, tenso como um arco retesado.",
)
```

Contradição com `core/prompts/story_continuation.txt:18-19`:
> Rules:
> - Continue the story in the same language as the user_input

O prompt real (Anthropic/local) segue essa regra; o Fake não. Se um teste
enviar `user_input` em inglês, o Fake retorna texto em português com o input
inglês embutido — mistura estranha.

## Risco

- **Testes cross-language ficam confusos**: alguém escrevendo um novo teste com
  input em inglês recebe output PT e pode assumir bug real quando é só o Fake.
- **Não crasharia produção** — o Fake nunca roda em produção.
- **Regressão de determinismo se corrigir mal**: se alguém tentar "detectar
  idioma" no Fake, quebra o determinismo (a detecção pode não ser estável).

## Fix sugerido

Opção A (simples, mantém determinismo): adicionar comentário reconhecendo a
limitação:
```python
# Templates são só em PT — dev language do projeto. Se testar cross-language,
# o output vai misturar (PT template + user_input em outra língua) — aceitável
# porque o Fake não é o narrador real; é wiring test.
_TEMPLATES: tuple[str, ...] = (...)
```

Opção B (mais elaborada): dois pools de templates, escolha por deteção simples
(primeira palavra vs stopwords) — mas quebra determinismo e adiciona complexidade
não-justificada pra portfólio.

Opção C (compromisso): manter PT, mas mudar templates de "sensory frase densa"
pra "eco puro" que preserva idioma:
```python
_TEMPLATES: tuple[str, ...] = (
    "[Fake narration seed {seed}] {echo}",
    "[Turn {seed}] {echo}",
    ...
)
```
Mais estéril mas language-neutral. Cuidado: pode enviesar retrieval (templates
todos com prefixo "[Fake ..." pontuam alto em similaridade).

**Recomendação**: A. Documentar a limitação, seguir em frente.

## Referências

- N/A.
