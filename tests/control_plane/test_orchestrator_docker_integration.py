from __future__ import annotations

import importlib
import uuid
from pathlib import Path

import pytest
from docker.errors import DockerException, ImageNotFound, NotFound
from fastapi.testclient import TestClient

from orchestrator.docker_client import SAEP_MANAGED_LABEL, SAEP_SANDBOX_ID_LABEL

pytestmark = pytest.mark.integration


def docker_client_or_skip():
    """Return a Docker client when Docker and the local sandbox image are available."""
    import docker

    try:
        client = docker.from_env()
        client.ping()
        client.images.get("saep-sandbox:local")
    except ImageNotFound:
        pytest.skip("saep-sandbox:local image is not built; run `make build` first")
    except DockerException as exc:
        pytest.skip(f"Docker is not available: {exc}")
    return client


def load_real_app(monkeypatch, tmp_path: Path):
    """Reload the orchestrator with a temporary DB/workspace and real Docker client."""
    monkeypatch.setenv("SAEP_REGISTRY_DB", (tmp_path / "registry.sqlite3").as_posix())
    monkeypatch.setenv("SAEP_WORKSPACES_DIR", (tmp_path / "workspaces").as_posix())
    monkeypatch.setenv("SAEP_INTERNAL_TOKEN", "test-token")
    monkeypatch.setenv("SAEP_SANDBOX_IMAGE", "saep-sandbox:local")

    import orchestrator.main as main

    module = importlib.reload(main)
    module.initialize()
    return module.app


def test_docker_lifecycle_create_health_delete(monkeypatch, tmp_path: Path) -> None:
    """Create, inspect, and delete a real Docker sandbox through the API."""
    docker_client = docker_client_or_skip()
    app = load_real_app(monkeypatch, tmp_path)
    client = TestClient(app)
    headers = {"X-SAEP-Internal-Token": "test-token"}
    created_body: dict | None = None

    try:
        created = client.post("/sandbox/create", headers=headers)
        assert created.status_code == 200
        created_body = created.json()

        container = docker_client.containers.get(created_body["container_id"])
        assert container.labels[SAEP_MANAGED_LABEL] == "true"
        assert container.labels[SAEP_SANDBOX_ID_LABEL] == created_body["sandbox_id"]

        health = client.get(f"/sandbox/{created_body['sandbox_id']}/health", headers=headers)
        assert health.status_code == 200
        assert health.json()["healthy"] is True
        assert health.json()["status"] == "running"
        assert health.json()["metrics"] == {"cpu_percent": None, "memory_bytes": None}

        deleted = client.delete(f"/sandbox/{created_body['sandbox_id']}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json() == {"sandbox_id": created_body["sandbox_id"], "status": "destroyed"}

        with pytest.raises(NotFound):
            docker_client.containers.get(created_body["container_id"])
    finally:
        if created_body:
            try:
                docker_client.containers.get(created_body["container_id"]).remove(force=True)
            except NotFound:
                pass


def test_reconciliation_removes_orphan_managed_container(monkeypatch, tmp_path: Path) -> None:
    """Startup reconciliation should remove managed containers without DB rows."""
    docker_client = docker_client_or_skip()
    sandbox_id = f"orphan-{uuid.uuid4().hex}"
    container = docker_client.containers.run(
        "saep-sandbox:local",
        detach=True,
        name=f"saep-{sandbox_id}",
        labels={SAEP_MANAGED_LABEL: "true", SAEP_SANDBOX_ID_LABEL: sandbox_id},
    )

    try:
        load_real_app(monkeypatch, tmp_path)

        with pytest.raises(NotFound):
            docker_client.containers.get(container.id)
    finally:
        try:
            docker_client.containers.get(container.id).remove(force=True)
        except NotFound:
            pass
