from __future__ import annotations

import stat
from pathlib import Path

from orchestrator.config import Settings
from orchestrator.docker_client import DockerSandboxClient


class FakeContainer:
    id = "container-id"
    name = "saep-sandbox-id"
    status = "running"


class FakeContainers:
    def __init__(self) -> None:
        self.run_calls: list[dict] = []

    def run(self, *args, **kwargs) -> FakeContainer:
        self.run_calls.append({"args": args, "kwargs": kwargs})
        return FakeContainer()


class FakeDockerClient:
    def __init__(self) -> None:
        self.containers = FakeContainers()


def test_create_container_makes_workspace_writable_for_non_root_agent(monkeypatch, tmp_path: Path) -> None:
    """Linux bind mounts need host write bits for the non-root sandbox user."""
    fake_docker = FakeDockerClient()
    monkeypatch.setattr("orchestrator.docker_client.docker.from_env", lambda: fake_docker)
    client = DockerSandboxClient(settings(tmp_path))
    workspace = tmp_path / "workspaces" / "sandbox-id"

    client.create_container("sandbox-id", workspace)

    assert workspace.stat().st_mode & stat.S_IWOTH
    assert fake_docker.containers.run_calls[0]["kwargs"]["volumes"] == {
        workspace.resolve().as_posix(): {"bind": "/workspace", "mode": "rw"}
    }


def settings(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=9999,
        sandbox_image="saep-sandbox:local",
        registry_db=tmp_path / "registry.sqlite3",
        workspaces_dir=tmp_path / "workspaces",
        internal_token="test-token",
        exec_timeout_seconds=300,
        container_memory="1g",
        container_cpus=1.0,
    )
