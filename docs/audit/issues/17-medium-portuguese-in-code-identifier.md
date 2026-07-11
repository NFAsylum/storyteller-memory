# `_COOCCURRENCE = "co-ocorrencia"` viola "inglês em código"

**Severity:** Medium
**Priority:** P2
**Category:** Code-guidelines
**Source:** `core/memory/reflection.py:36`, `core/memory/reflection.py:169`, `core/memory/reflection.py:178`, `tests/test_reflection.py:125`

## Descrição

Convenção do projeto (`CLAUDE.md:115-117`):
> - Português em docs, comentários pro humano, commits em português OK
> - Inglês em código, docstrings, e prompts LLM

`reflection.py:36` define:
```python
_COOCCURRENCE = "co-ocorrencia"  # Portuguese identifier value
```

Isso é usado como o `kind` da Relation em duas linhas:
```python
# reflection.py:169
Relation(
    ...,
    kind=_COOCCURRENCE,
    ...
)

# reflection.py:178
{r.a_character_id, r.b_character_id} == {a_id, b_id} and r.kind == _COOCCURRENCE
```

E o teste (`test_reflection.py:125`) espera essa string:
```python
assert rels[0].kind == "co-ocorrencia"
```

Duas violações:
1. Valor persistido no banco (`kind` column) em português — mistura com padrões
   como `"rivalidade"` que aparecem em `test_reflection.py:157` (também PT). Mas
   também com `"rivalry"` (inglês) em `test_world_state.py:79`. **Inconsistência.**
2. Sem "ç" — a palavra correta em PT é "co-ocorrência". Já cortada a acentuação
   sugere o autor sabia que era mistura problemática mas escolheu um meio-termo.

Outros lugares onde textos em português vazam pro `code path` (não são pura data
label):
- `_STOPWORDS` (linhas 38-58): mistura PT ("Nos", "Aos", "Uma", "Nas", "Depois",
  "Quando", "Enquanto") com EN ("Turn", "Player", "Narrator"). Aqui é
  data (lista de stopwords) — aceitável, mas comentário deveria justificar.
- `_LOCATION_RE = re.compile(r"(?i:castelo|reino|cidade|vila|forte|torre|porto)\s+de\s+(...)")` (linha 34)
  — regex em PT. Sem essa keyword em EN. Justificável (o domínio é narrativas
  em PT), mas ligado ao guardrail de "inglês em código".
- `_PLAYER_PREFIX = "Player:"` — inglês. OK.

## Risco

- **Mistura difícil de auditar**: quando um dia adicionarem `"conflito"` vs
  `"conflict"` como kind de relation, o dedupe (`_persist_relations`) trata como
  diferentes → duplicatas semânticas.
- **Portabilidade**: se algum dia rodarem cenários em inglês, o
  `_LOCATION_RE` para de funcionar. Isso é limitação conhecida mas não
  documentada em `reflection.py`.
- **Guideline violation**: `CLAUDE.md` é clara. Cada infração fica como precedente
  pro próximo dev "OK misturar às vezes".

## Fix sugerido

1. **Renomear constante e valor**:
   ```python
   _COOCCURRENCE = "co-occurrence"  # kind identifier stored in DB
   ```

2. **Migration Alembic** pra atualizar rows existentes:
   ```python
   def upgrade():
       op.execute(text("UPDATE relations SET kind = 'co-occurrence' WHERE kind = 'co-ocorrencia'"))
   ```

3. **Atualizar teste** pra bater com o novo valor.

4. **Adicionar comentário justificativo** onde PT em código é intencional:
   ```python
   # Regex em português: o domínio de story worlds do MVP é em português-BR;
   # se um dia rodar cenários em inglês, adicionar variante (castle|kingdom|...).
   _LOCATION_RE = re.compile(...)

   # Stopwords: mistura EN (labels estruturais Turn/Player/Narrator) + PT
   # (starters comuns Nas/Nos/Aos/Uma) porque o corpus é PT-BR mas as labels são EN.
   _STOPWORDS = frozenset({...})
   ```

5. Sweep de `test_reflection.py:157` (`"kind": "rivalidade"`) — considerar
   `"rivalry"` para alinhar. Não bloqueante porque é fixture de teste.

## Referências

- `CLAUDE.md:115-117` (a diretriz que este issue viola).
