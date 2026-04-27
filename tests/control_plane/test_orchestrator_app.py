from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def load_app(monkeypatch, tmp_path: Path):
    """Reload the app after setting env vars so module-level settings refresh."""
    monkeypatch.setenv("SAEP_REGISTRY_DB", (tmp_path / "registry.sqlite3").as_posix())
    monkeypatch.setenv("SAEP_INTERNAL_TOKEN", "test-token")

    import orchestrator.main as main

    module = importlib.reload(main)
    module.initialize()
    return module.app


def test_healthz_does_not_require_auth(monkeypatch, tmp_path: Path) -> None:
    """The process health endpoint stays unauthenticated for local smoke tests."""
    app = load_app(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_sandbox_routes_reject_missing_internal_token(monkeypatch, tmp_path: Path) -> None:
    """Docker-control routes should reject callers without the internal token."""
    app = load_app(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.post("/sandbox/create")

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "unauthorized"


def test_sandbox_routes_accept_internal_token_and_return_placeholders(monkeypatch, tmp_path: Path) -> None:
    """Phase 1 wires route/auth shape while leaving Docker behavior for Phase 2."""
    app = load_app(monkeypatch, tmp_path)
    client = TestClient(app)
    headers = {"X-SAEP-Internal-Token": "test-token"}

    responses = [
        client.post("/sandbox/create", headers=headers),
        client.get("/sandbox/sandbox-1/health", headers=headers),
        client.post("/sandbox/sandbox-1/exec", headers=headers, json={"command": ["echo", "hi"]}),
        client.delete("/sandbox/sandbox-1", headers=headers),
    ]

    assert [response.status_code for response in responses] == [501, 501, 501, 501]
    assert all(response.json()["detail"]["error"] == "not_implemented" for response in responses)


def test_sandbox_routes_allow_requests_when_internal_token_unset(monkeypatch, tmp_path: Path) -> None:
    """An unset token keeps local skeleton development possible."""
    monkeypatch.setenv("SAEP_REGISTRY_DB", (tmp_path / "registry.sqlite3").as_posix())
    monkeypatch.delenv("SAEP_INTERNAL_TOKEN", raising=False)

    import orchestrator.main as main

    module = importlib.reload(main)
    module.initialize()
    client = TestClient(module.app)

    response = client.post("/sandbox/create")

    assert response.status_code == 501
    assert response.json()["detail"]["error"] == "not_implemented"
