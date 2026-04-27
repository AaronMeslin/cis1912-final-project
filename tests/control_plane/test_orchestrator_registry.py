from __future__ import annotations

from pathlib import Path

from orchestrator.config import load_settings
from orchestrator.registry import SandboxRegistry


def test_registry_insert_get_list_update_delete(tmp_path: Path) -> None:
    """Registry rows should support the full create/read/update/delete cycle."""
    registry = SandboxRegistry(tmp_path / "registry.sqlite3")
    registry.init_db()

    inserted = registry.insert_sandbox(
        sandbox_id="sandbox-1",
        container_id="container-1",
        container_name="saep-sandbox-1",
        status="running",
        image="saep-sandbox:local",
        workspace_path="/tmp/workspace",
    )

    assert inserted.id == "sandbox-1"
    assert inserted.status == "running"
    assert inserted.created_at
    assert inserted.updated_at

    fetched = registry.get_sandbox("sandbox-1")
    assert fetched == inserted
    assert registry.list_sandboxes() == [inserted]

    assert registry.update_container("sandbox-1", "container-2", "saep-sandbox-2", "running")
    with_container = registry.get_sandbox("sandbox-1")
    assert with_container is not None
    assert with_container.container_id == "container-2"
    assert with_container.container_name == "saep-sandbox-2"
    assert registry.update_status("sandbox-1", "stopping")
    updated = registry.get_sandbox("sandbox-1")
    assert updated is not None
    assert updated.status == "stopping"
    assert not registry.update_status("missing", "stopping")

    assert registry.delete_sandbox("sandbox-1")
    assert registry.get_sandbox("sandbox-1") is None
    assert not registry.delete_sandbox("missing")


def test_load_settings_reads_environment(monkeypatch, tmp_path: Path) -> None:
    """Environment variables should override local orchestrator defaults."""
    monkeypatch.setenv("SAEP_ORCHESTRATOR_HOST", "127.0.0.2")
    monkeypatch.setenv("SAEP_ORCHESTRATOR_PORT", "9998")
    monkeypatch.setenv("SAEP_SANDBOX_IMAGE", "custom:local")
    monkeypatch.setenv("SAEP_REGISTRY_DB", (tmp_path / "db.sqlite3").as_posix())
    monkeypatch.setenv("SAEP_WORKSPACES_DIR", (tmp_path / "workspaces").as_posix())
    monkeypatch.setenv("SAEP_INTERNAL_TOKEN", "token")
    monkeypatch.setenv("SAEP_EXEC_TIMEOUT_SECONDS", "42")
    monkeypatch.setenv("SAEP_CONTAINER_MEMORY", "512m")
    monkeypatch.setenv("SAEP_CONTAINER_CPUS", "0.5")

    settings = load_settings()

    assert settings.host == "127.0.0.2"
    assert settings.port == 9998
    assert settings.sandbox_image == "custom:local"
    assert settings.registry_db == tmp_path / "db.sqlite3"
    assert settings.workspaces_dir == tmp_path / "workspaces"
    assert settings.internal_token == "token"
    assert settings.exec_timeout_seconds == 42
    assert settings.container_memory == "512m"
    assert settings.container_cpus == 0.5
