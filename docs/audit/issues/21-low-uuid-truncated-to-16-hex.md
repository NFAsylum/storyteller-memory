# `session_id = uuid.uuid4().hex[:16]` — 64 bits em vez de 128

**Severity:** Low
**Priority:** P3
**Category:** Security
**Source:** `api/main.py:97`

## Descrição

```python
session_id = uuid.uuid4().hex[:16]
```

`uuid.uuid4()` gera 128 bits. Truncar para 16 hex chars = 64 bits deixa 2⁶⁴ =
1.8×10¹⁹ IDs possíveis. Nunca é suficiente pra evitar colisões em qualquer
escala, mas o problema real é enumeração.

Interação com issue 02 (auth): sem autenticação, session_id é o "segredo". 64
bits contra ataque de força bruta:
- 1 request/segundo: 5 × 10¹¹ anos pra enumerar tudo.
- 10k requests/segundo (via botnet): 60 milhões de anos.

Na prática nenhum atacante enumera. Mas boas práticas dizem 128 bits para
IDs que funcionam como capabilities (o único gatekeeper de acesso).

## Risco

- **Baixo hoje.** Uso previsível é interno.
- **Cresce se deploy Sprint 6 for público** — combina com issue 02 (sem auth) e
  faz o session_id ser o único bearer token. Aí 128 bits vira importante.
- **Colisão**: com 10⁶ sessões, probabilidade de colisão é ~2.7×10⁻⁷. Não
  material pro portfólio.

## Fix sugerido

Trocar por `uuid.uuid4().hex` inteiro (32 chars, 128 bits):
```python
session_id = uuid.uuid4().hex
```

Ou usar `secrets.token_hex(16)` (mesma coisa, mas mais explícito sobre segurança):
```python
import secrets
session_id = secrets.token_hex(16)  # 32 chars = 128 bits, crypto-safe
```

Verificar que `String(64)` no schema (`world_state.py:70`) ainda cabe (32 < 64,
OK).

Migration: para sessões existentes com IDs de 16 chars não há impacto — apenas
novas ficam mais longas.

## Referências

- OWASP Session Management: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- Python `secrets.token_hex`: https://docs.python.org/3/library/secrets.html
