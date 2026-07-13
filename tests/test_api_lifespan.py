"""T-INFRA.1: the lifespan handler warms the backend at startup (on the main thread)."""

import pytest
from fastapi.testclient import TestClient

import api.deps as deps
from api.main import app


def test_lifespan_builds_backend_on_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub build_backend so we don't construct the real (72s) mem0 in the test.
    sentinel = object()
    monkeypatch.setattr(deps, "build_backend", lambda: sentinel)
    monkeypatch.setattr(deps, "_backend", None)

    assert deps._backend is None
    with TestClient(app):  # entering the context runs the lifespan startup
        assert deps._backend is sentinel
