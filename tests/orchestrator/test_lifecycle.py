import json
from dataclasses import dataclass

import pytest

from orchestrator.docker import CommandResult, DockerSandboxManager, SandboxNotFound
from orchestrator.server import route_request


@dataclass
class FakeRunner:
    inspect_payload: dict | None = None
    fail_create: bool = False
    fail_inspect: bool = False

    def __post_init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, args: list[str]) -> CommandResult:
        self.commands.append(args)
        if args[:2] == ["docker", "run"]:
            if self.fail_create:
                return CommandResult(1, "", "docker unavailable")
            return CommandResult(0, "container-123\n", "")
        if args[:2] == ["docker", "inspect"]:
            if self.fail_inspect:
                return CommandResult(1, "", "not found")
            payload = self.inspect_payload or {
                "Id": "container-123",
                "Name": "/saep-container-123",
                "State": {"Status": "running", "Health": {"Status": "healthy"}},
            }
            return CommandResult(0, json.dumps(payload), "")
        if args[:2] == ["docker", "rm"]:
            return CommandResult(0, "container-123\n", "")
        raise AssertionError(f"unexpected command: {args}")


def test_manager_creates_sandbox_with_expected_runtime_contract() -> None:
    runner = FakeRunner()
    manager = DockerSandboxManager(runner=runner, id_factory=lambda: "container-123")

    sandbox = manager.create()

    assert sandbox["sandboxId"] == "container-123"
    assert sandbox["status"] == "created"
    assert runner.commands[0] == [
        "docker",
        "run",
        "-d",
        "--name",
        "saep-container-123",
        "--label",
        "saep.sandbox.id=container-123",
        "--workdir",
        "/workspace",
        "saep-sandbox:local",
        "sleep",
        "infinity",
    ]


def test_manager_reads_health_from_docker_inspect() -> None:
    runner = FakeRunner()
    manager = DockerSandboxManager(runner=runner)

    health = manager.health("container-123")

    assert health == {
        "sandboxId": "container-123",
        "containerName": "saep-container-123",
        "containerId": "container-123",
        "healthy": True,
        "status": "running",
        "health": "healthy",
    }


def test_manager_maps_missing_container_to_not_found() -> None:
    manager = DockerSandboxManager(runner=FakeRunner(fail_inspect=True))

    with pytest.raises(SandboxNotFound):
        manager.health("missing")


def test_route_request_handles_lifecycle_json() -> None:
    manager = DockerSandboxManager(runner=FakeRunner(), id_factory=lambda: "container-123")

    create_status, create_body = route_request("POST", "/sandboxes", b"", manager)
    health_status, health_body = route_request("GET", "/sandboxes/container-123/health", b"", manager)
    delete_status, delete_body = route_request("DELETE", "/sandboxes/container-123", b"", manager)

    assert create_status == 201
    assert create_body["sandboxId"] == "container-123"
    assert health_status == 200
    assert health_body["healthy"] is True
    assert delete_status == 200
    assert delete_body == {"sandboxId": "container-123", "status": "destroyed"}


def test_route_request_returns_404_for_missing_sandbox() -> None:
    manager = DockerSandboxManager(runner=FakeRunner(fail_inspect=True))

    status, body = route_request("GET", "/sandboxes/missing/health", b"", manager)

    assert status == 404
    assert body == {"error": "not_found", "sandboxId": "missing"}


def test_route_request_returns_502_when_create_fails() -> None:
    manager = DockerSandboxManager(runner=FakeRunner(fail_create=True))

    status, body = route_request("POST", "/sandboxes", b"", manager)

    assert status == 502
    assert body == {"error": "orchestrator_error", "message": "docker unavailable"}
