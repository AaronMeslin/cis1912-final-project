from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.models.containers import Container

from .config import Settings

SAEP_MANAGED_LABEL = "saep.managed"
SAEP_SANDBOX_ID_LABEL = "saep.sandbox_id"


class DockerUnavailable(RuntimeError):
    """Raised when the local Docker daemon cannot be reached."""


class SandboxContainerNotFound(RuntimeError):
    """Raised when a registry row points at a missing Docker container."""


class SandboxImageNotFound(RuntimeError):
    """Raised when the configured sandbox image has not been built locally."""


@dataclass(frozen=True)
class ContainerHandle:
    """Stable container metadata returned to the API layer."""

    id: str
    name: str
    status: str


@dataclass(frozen=True)
class ContainerHealth:
    """Runtime state reported for one Docker container."""

    status: str
    healthy: bool
    cpu_percent: float | None = None
    memory_bytes: int | None = None


class DockerSandboxClient:
    """Project-specific wrapper around the Docker SDK."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        try:
            self.client = docker.from_env()
        except DockerException as exc:
            raise DockerUnavailable(str(exc)) from exc

    def create_container(self, sandbox_id: str, workspace_path: Path) -> ContainerHandle:
        """Create and start a sandbox container for one sandbox ID."""
        workspace_path.mkdir(parents=True, exist_ok=True)
        container_name = self.container_name(sandbox_id)
        try:
            container = self.client.containers.run(
                self.settings.sandbox_image,
                detach=True,
                name=container_name,
                working_dir="/workspace",
                volumes={workspace_path.resolve().as_posix(): {"bind": "/workspace", "mode": "rw"}},
                labels={
                    SAEP_MANAGED_LABEL: "true",
                    SAEP_SANDBOX_ID_LABEL: sandbox_id,
                },
                mem_limit=self.settings.container_memory,
                nano_cpus=int(self.settings.container_cpus * 1_000_000_000),
            )
        except ImageNotFound as exc:
            raise SandboxImageNotFound(self.settings.sandbox_image) from exc
        except DockerException as exc:
            raise RuntimeError(f"failed to create sandbox container: {exc}") from exc
        return self._handle(container)

    def get_health(self, container_id: str) -> ContainerHealth:
        """Inspect a container and return coarse health information."""
        container = self._get_container(container_id)
        container.reload()
        status = container.status
        return ContainerHealth(status=status, healthy=status == "running")

    def destroy_container(self, container_id: str) -> None:
        """Stop and remove a sandbox container if it still exists."""
        try:
            container = self._get_container(container_id)
        except SandboxContainerNotFound:
            return
        try:
            container.remove(force=True)
        except DockerException as exc:
            raise RuntimeError(f"failed to remove sandbox container: {exc}") from exc

    def list_managed_containers(self) -> list[ContainerHandle]:
        """List containers labeled as managed by this orchestrator."""
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"label": f"{SAEP_MANAGED_LABEL}=true"},
            )
        except DockerException as exc:
            raise RuntimeError(f"failed to list sandbox containers: {exc}") from exc
        return [self._handle(container) for container in containers]

    def remove_container_by_id(self, container_id: str) -> None:
        """Remove a Docker container by ID during reconciliation cleanup."""
        self.destroy_container(container_id)

    @staticmethod
    def container_name(sandbox_id: str) -> str:
        """Return the deterministic Docker container name for a sandbox."""
        return f"saep-{sandbox_id}"

    def _get_container(self, container_id: str) -> Container:
        try:
            return self.client.containers.get(container_id)
        except NotFound as exc:
            raise SandboxContainerNotFound(container_id) from exc
        except DockerException as exc:
            raise RuntimeError(f"failed to inspect sandbox container: {exc}") from exc

    @staticmethod
    def _handle(container: Container) -> ContainerHandle:
        return ContainerHandle(id=container.id, name=container.name, status=container.status)
