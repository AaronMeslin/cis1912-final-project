from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class SandboxNotFound(Exception):
    pass


Runner = Callable[[list[str]], CommandResult]


def subprocess_runner(args: list[str]) -> CommandResult:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


class DockerSandboxManager:
    def __init__(
        self,
        runner: Runner = subprocess_runner,
        image: str = "saep-sandbox:local",
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.runner = runner
        self.image = image
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def create(self) -> dict[str, str]:
        sandbox_id = self.id_factory()
        name = self._container_name(sandbox_id)
        result = self.runner(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--label",
                f"saep.sandbox.id={sandbox_id}",
                "--workdir",
                "/workspace",
                self.image,
                "sleep",
                "infinity",
            ]
        )
        self._raise_for_failure(result)
        return {"sandboxId": sandbox_id, "containerId": result.stdout.strip(), "status": "created"}

    def health(self, sandbox_id: str) -> dict[str, object]:
        info = self._inspect(sandbox_id)
        state = info.get("State", {})
        health = state.get("Health", {}).get("Status")
        status = state.get("Status", "unknown")
        return {
            "sandboxId": sandbox_id,
            "containerName": self._container_name(sandbox_id),
            "containerId": info.get("Id", ""),
            "healthy": status == "running" and health in (None, "healthy"),
            "status": status,
            "health": health,
        }

    def destroy(self, sandbox_id: str) -> dict[str, str]:
        result = self.runner(["docker", "rm", "-f", self._container_name(sandbox_id)])
        if result.returncode != 0:
            raise SandboxNotFound(sandbox_id)
        return {"sandboxId": sandbox_id, "status": "destroyed"}

    def _inspect(self, sandbox_id: str) -> dict:
        result = self.runner(["docker", "inspect", self._container_name(sandbox_id)])
        if result.returncode != 0:
            raise SandboxNotFound(sandbox_id)
        payload = json.loads(result.stdout)
        return payload[0] if isinstance(payload, list) else payload

    def _container_name(self, sandbox_id: str) -> str:
        return f"saep-{sandbox_id}"

    @staticmethod
    def _raise_for_failure(result: CommandResult) -> None:
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "docker command failed")
