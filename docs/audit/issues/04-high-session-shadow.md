# `class Session(Base)` sombreia `sqlalchemy.orm.Session` no type hint de `WorldState`

**Severity:** High
**Priority:** P1 (essa sprint)
**Category:** Logic
**Source:** `core/memory/world_state.py:14`, `core/memory/world_state.py:65-74`, `core/memory/world_state.py:97`

## Descrição

`core/memory/world_state.py` importa `Session` de SQLAlchemy no topo:

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
```

Mais adiante define um modelo ORM com o mesmo nome:

```python
class Session(Base):
    """A story session (the UI's left-column list). id doubles as the mem0/world_state scope."""
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ...
```

Depois disso, o construtor de `WorldState` usa `Session` como type hint:

```python
class WorldState:
    def __init__(self, session: Session) -> None:
        self._session = session
```

Na hora que essa type hint é resolvida (`from __future__ import annotations` está
ativo, então é lazy), o nome `Session` no escopo do módulo já foi rebindado para
`class Session(Base)` — o **modelo ORM**, não a Session do SQLAlchemy.

Todos os callers passam de fato uma `sqlalchemy.orm.Session` (verificado em
`api/main.py:139` via `backend.session_factory()`, `core/db.py`,
`tests/test_world_state.py:26-27`). O runtime funciona porque type hints não são
validadas em tempo de execução, mas:

- `mypy` reporta erro em qualquer chamada `WorldState(db)`.
- Um IDE que segue a hint mostra atributos errados (`.name`, `.brief`, `.id`)
  em vez dos métodos reais (`.add`, `.commit`, `.get`).
- Refactor futuro que confie na hint pode passar o objeto errado — bug silencioso.

## Risco

- Falso positivo no code review: alguém procurando "onde é usado sqlalchemy.orm.Session"
  encontra o import + a definição do model e conclui erroneamente que o construtor
  espera o modelo ORM Session (uma linha do DB), não uma sessão de banco.
- Se alguém alterar `WorldState.__init__` para aceitar de fato o model Session
  (por exemplo, pra tomar o `owner_id` da row, ver issue 02), o refactor "cria
  sentido" mas quebra todos os call sites em runtime.
- mypy report ruidoso reduz utilidade da tipagem estática.

## Fix sugerido

Renomear o import ou o model. Padrão mais comum: aliaar o import.

Opção A (menor diff, preserva o nome do model):
```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import Session as DbSession

class Session(Base):  # unchanged
    ...

class WorldState:
    def __init__(self, session: DbSession) -> None:
        self._session = session
```

Opção B (renomear o modelo pra `StorySession` — mais claro semanticamente, mas
diff maior porque `api/main.py`, migration 0002 e testes usam `Session`):
```python
class StorySession(Base):
    __tablename__ = "sessions"
    ...
```

Recomendação: **Opção A**. Já existe precedente no repo — `api/deps.py:9` usa
`from sqlalchemy.orm import Session as DbSession`. Alinhar `world_state.py` com
essa convenção.

## Referências

- PEP 484 (type hints): https://peps.python.org/pep-0484/
- SQLAlchemy Session: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
