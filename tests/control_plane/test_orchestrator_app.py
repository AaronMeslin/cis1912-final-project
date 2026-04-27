from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient
from orchestrator.docker_client import ContainerHandle, ContainerHealth


class FakeDockerClient:
    """In-memory Docker stand-in for route-level tests."""

    def __init__(self) -> None:
        self.created: dict[str, ContainerHandle] = {}
        self.destroyed: list[str] = []

    def container_name(self, sandbox_id: str) -> str:
        return f"saep-{sandbox_id}"

    def create_container(self, sandbox_id: str, workspace_path: Path) -> ContainerHandle:
        workspace_path.mkdir(parents=True, exist_ok=True)
        handle = ContainerHandle(id=f"container-{sandbox_id}", name=self.container_name(sandbox_id), status="running")
        self.created[sandbox_id] = handle
        return handle

    def get_health(self, container_id: str) -> ContainerHealth:
        return ContainerHealth(status="running", healthy=True)

    def destroy_container(self, container_id: str) -> None:
        self.destroyed.append(container_id)


def load_app(monkeypatch, tmp_path: Path, fake_client: FakeDockerClient | None = None):
    """Reload the app after setting env vars so module-level settings refresh."""
    monkeypatch.setenv("SAEP_REGISTRY_DB", (tmp_path / "registry.sqlite3").as_posix())
    monkeypatch.setenv("SAEP_WORKSPACES_DIR", (tmp_path / "workspaces").as_posix())
    monkeypatch.setenv("SAEP_INTERNAL_TOKEN", "test-token")

    import orchestrator.main as main

    module = importlib.reload(main)
    module.registry.init_db()
    module.docker_client = fake_client or FakeDockerClient()
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


def test_create_sandbox_accepts_internal_token_and_registers_container(monkeypatch, tmp_path: Path) -> None:
    """The create route should coordinate registry and Docker client state."""
    app = load_app(monkeypatch, tmp_path)
    client = TestClient(app)
    headers = {"X-SAEP-Internal-Token": "test-token"}

    response = client.post("/sandbox/create", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sandbox_id"]
    assert body["container_id"] == f"container-{body['sandbox_id']}"
    assert body["status"] == "running"


def test_health_and_delete_use_registered_container(monkeypatch, tmp_path: Path) -> None:
    """Health and delete should operate on the registry row created earlier."""
    fake = FakeDockerClient()
    app = load_app(monkeypatch, tmp_path, fake)
    client = TestClient(app)
    headers = {"X-SAEP-Internal-Token": "test-token"}
    created = client.post("/sandbox/create", headers=headers).json()

    health = client.get(f"/sandbox/{created['sandbox_id']}/health", headers=headers)

    assert health.status_code == 200
    assert health.json()["healthy"] is True
    assert health.json()["status"] == "running"
    assert health.json()["metrics"] == {"cpu_percent": None, "memory_bytes": None}

    deleted = client.delete(f"/sandbox/{created['sandbox_id']}", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json() == {"sandbox_id": created["sandbox_id"], "status": "destroyed"}
    assert fake.destroyed == [created["container_id"]]


def test_missing_sandbox_returns_404(monkeypatch, tmp_path: Path) -> None:
    """Missing sandbox IDs should return a stable not_found response."""
    app = load_app(monkeypatch, tmp_path)
    client = TestClient(app)
    headers = {"X-SAEP-Internal-Token": "test-token"}

    health = client.get("/sandbox/missing/health", headers=headers)
    deleted = client.delete("/sandbox/missing", headers=headers)

    assert health.status_code == 404
    assert health.json()["detail"]["error"] == "not_found"
    assert deleted.status_code == 404
    assert deleted.json()["detail"]["error"] == "not_found"


def test_exec_route_remains_placeholder(monkeypatch, tmp_path: Path) -> None:
    """Phase 2 intentionally leaves exec for the locking/SSE phase."""
    app = load_app(monkeypatch, tmp_path)
    client = TestClient(app)
    headers = {"X-SAEP-Internal-Token": "test-token"}

    response = client.post("/sandbox/sandbox-1/exec", headers=headers, json={"command": ["echo", "hi"]})

    assert response.status_code == 501
    assert response.json()["detail"]["error"] == "not_implemented"


def test_sandbox_routes_allow_requests_when_internal_token_unset(monkeypatch, tmp_path: Path) -> None:
    """An unset token keeps local skeleton development possible."""
    monkeypatch.setenv("SAEP_REGISTRY_DB", (tmp_path / "registry.sqlite3").as_posix())
    monkeypatch.delenv("SAEP_INTERNAL_TOKEN", raising=False)

    import orchestrator.main as main

    module = importlib.reload(main)
    module.registry.init_db()
    module.docker_client = FakeDockerClient()
    client = TestClient(module.app)

    response = client.post("/sandbox/create")

    assert response.status_code == 200
