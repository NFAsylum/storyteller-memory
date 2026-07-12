# `DELETE /sessions/{id}` commita DB antes de limpar mem0

**Severity:** High
**Priority:** P1
**Category:** Logic
**Source:** `api/main.py:126-134`

## Descrição

```python
@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, backend: Backend = Depends(get_backend)) -> None:
    with backend.session_factory() as db:
        _get_session(db, session_id)
        for model in (Turn, StoryBeat, Relation, Location, Character):
            db.execute(delete(model).where(model.session_id == session_id))
        db.execute(delete(Session).where(Session.id == session_id))
        db.commit()
    backend.memory_for(session_id).clear()
```

Ordem:
1. Deleta as 6 tabelas do SQL.
2. `db.commit()` — SQL persistido.
3. `backend.memory_for(session_id).clear()` — chama mem0.delete_all.

Se o passo 3 lançar (mem0 offline, disco cheio, network hiccup, faiss corrompida),
o SQL já está commitado. A sessão desaparece da UI mas as memórias em mem0
persistem órfãs no store FAISS local. Não há retry, não há log, o cliente recebe
500 sem indicação clara.

## Risco

Cenários:
- **Retry do cliente**: o UI reenvia o DELETE. Passo 1 falha em `_get_session`
  com 404 (sessão já deletada), mas mem0 permanece órfão para sempre.
- **Enumeração**: um scan por `POST /sessions/{orphaned_session_id}/turn` ainda
  pode chegar até mem0 e retomar contexto de uma sessão "deletada" — bug de
  privacidade se o Sprint 6 for público.
- **FAISS disk bloat**: FAISS store não é auto-cleanup; órfãos crescem
  indefinidamente. Em runs de eval + UI misturados, `.mem0_data/faiss/` pode
  virar GBs sem que os arquivos referentes a sessões "deletadas" sejam removidos.
- **Inconsistência entre `GET /sessions` e mem0**: relatórios de "N sessões" no
  banco não batem com o número de vetores no faiss. Debug futuro é confuso.

## Fix sugerido

Opção A — limpar mem0 primeiro (fail loud antes de commit SQL):
```python
@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id, backend = Depends(get_backend)) -> None:
    with backend.session_factory() as db:
        _get_session(db, session_id)
        # Fail loudly here if mem0 is down — DB stays intact for retry.
        backend.memory_for(session_id).clear()
        for model in (Turn, StoryBeat, Relation, Location, Character):
            db.execute(delete(model).where(model.session_id == session_id))
        db.execute(delete(Session).where(Session.id == session_id))
        db.commit()
```

Trade-off: se o DB falhar (raro em SQLite local, possível em Postgres remoto), a
mem0 já foi limpa mas a sessão persiste no DB. Melhor que o cenário oposto porque
uma sessão "sem memória" é degradação graciosa (o próximo turno cria memórias
novas), enquanto "memórias órfãs" é vazamento silencioso.

Opção B — 2-fase com marcação:
1. Marcar `Session.deleted_at = now()` (soft delete) + commit.
2. Job background limpa mem0 + hard-delete DB depois. Idempotente.

Complexidade maior; provavelmente overkill pro portfólio.

**Recomendação**: Opção A + adicionar teste:
```python
def test_delete_fails_loud_if_mem0_clear_raises(client):
    tc, _ = client
    sid = _create(tc)
    # Force mem0 to raise:
    backend = app.dependency_overrides[get_backend]()
    class _ExplodingMem:
        session_id = sid
        def clear(self): raise RuntimeError("mem0 down")
    backend.memory_for = lambda _sid: _ExplodingMem()
    assert tc.delete(f"/sessions/{sid}").status_code == 500
    # DB row still exists (rollback preserved data)
    assert tc.get(f"/sessions/{sid}").status_code == 200
```

## Referências

- Two-phase commit patterns: https://microservices.io/patterns/data/saga.html
