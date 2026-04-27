from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, status

from .config import load_settings
from .docker_client import (
    DockerSandboxClient,
    SandboxContainerNotFound,
    SandboxImageNotFound,
)
from .models import CreateResponse, HealthMetrics, HealthResponse
from .registry import SandboxRegistry

settings = load_settings()
registry = SandboxRegistry(settings.registry_db)
docker_client: DockerSandboxClient | None = None


def initialize() -> None:
    """Initialize local orchestrator state on process startup."""
    global docker_client
    registry.init_db()
    docker_client = DockerSandboxClient(settings)
    reconcile_state(docker_client)


def reconcile_state(client: DockerSandboxClient) -> None:
    """Reconcile stale SQLite rows and orphaned Docker containers on startup."""
    records = {record.id: record for record in registry.list_sandboxes()}
    containers = client.list_managed_containers()
    container_ids = {container.id for container in containers}

    for container in containers:
        sandbox_id = container.name.removeprefix("saep-")
        if sandbox_id not in records:
            client.remove_container_by_id(container.id)

    for record in records.values():
        if record.container_id and record.container_id not in container_ids:
            registry.update_status(record.id, "error")


def get_docker_client() -> DockerSandboxClient:
    """Return the initialized Docker client or fail with a 503."""
    if docker_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "docker_unavailable", "message": "Docker client is not initialized"},
        )
    return docker_client


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan hook used to initialize the SQLite registry."""
    initialize()
    yield


app = FastAPI(title="SAEP Orchestrator", lifespan=lifespan)


def require_internal_token(x_saep_internal_token: str | None = Header(default=None)) -> None:
    """Protect Docker-control routes with an optional internal token."""
    if settings.internal_token is None:
        return
    if x_saep_internal_token != settings.internal_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "Invalid or missing internal token"},
        )


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    """Return process health for local development and smoke tests."""
    return {"ok": True}


@app.post("/sandbox/create", dependencies=[Depends(require_internal_token)])
def create_sandbox(client: DockerSandboxClient = Depends(get_docker_client)) -> CreateResponse:
    """Create and register a Docker sandbox."""
    sandbox_id = uuid.uuid4().hex
    workspace_path = settings.workspaces_dir / sandbox_id
    container_name = client.container_name(sandbox_id)
    registry.insert_sandbox(
        sandbox_id=sandbox_id,
        container_id="pending",
        container_name=container_name,
        status="creating",
        image=settings.sandbox_image,
        workspace_path=workspace_path.as_posix(),
    )
    try:
        container = client.create_container(sandbox_id, workspace_path)
    except SandboxImageNotFound as exc:
        registry.update_status(sandbox_id, "error")
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail={"error": "sandbox_image_not_found", "message": f"Sandbox image not found: {exc}"},
        ) from exc
    except Exception as exc:
        registry.update_status(sandbox_id, "error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "sandbox_create_failed", "message": str(exc)},
        ) from exc

    try:
        updated = registry.update_container(sandbox_id, container.id, container.name, "running")
        record = registry.get_sandbox(sandbox_id)
        if not updated or record is None:
            raise RuntimeError("registry row disappeared during create")
    except Exception as exc:
        client.destroy_container(container.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "registry_write_failed", "message": "Sandbox was created but registry update failed"},
        ) from exc
    return CreateResponse(
        sandbox_id=record.id,
        container_id=record.container_id,
        status=record.status,
        created_at=record.created_at,
    )


@app.get("/sandbox/{sandbox_id}/health", dependencies=[Depends(require_internal_token)])
def sandbox_health(
    sandbox_id: str,
    client: DockerSandboxClient = Depends(get_docker_client),
) -> HealthResponse:
    """Inspect Docker state for an existing sandbox."""
    record = registry.get_sandbox(sandbox_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Sandbox not found: {sandbox_id}"},
        )
    try:
        health = client.get_health(record.container_id)
    except SandboxContainerNotFound as exc:
        registry.update_status(sandbox_id, "error")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "container_not_found", "message": f"Sandbox container not found: {sandbox_id}"},
        ) from exc
    return HealthResponse(
        sandbox_id=record.id,
        healthy=health.healthy,
        status=health.status,
        created_at=record.created_at,
        metrics=HealthMetrics(cpu_percent=health.cpu_percent, memory_bytes=health.memory_bytes),
    )


@app.post("/sandbox/{sandbox_id}/exec", dependencies=[Depends(require_internal_token)])
def exec_sandbox(sandbox_id: str) -> None:
    """Placeholder for SSE command execution in the next phase."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"error": "not_implemented", "message": f"Sandbox exec is not implemented yet for {sandbox_id}"},
    )


@app.delete("/sandbox/{sandbox_id}", dependencies=[Depends(require_internal_token)])
def delete_sandbox(
    sandbox_id: str,
    client: DockerSandboxClient = Depends(get_docker_client),
) -> dict[str, str]:
    """Destroy a Docker sandbox and remove its registry row."""
    record = registry.get_sandbox(sandbox_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Sandbox not found: {sandbox_id}"},
        )
    registry.update_status(sandbox_id, "stopping")
    try:
        client.destroy_container(record.container_id)
    except Exception as exc:
        registry.update_status(sandbox_id, "error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "sandbox_destroy_failed", "message": str(exc)},
        ) from exc
    registry.delete_sandbox(sandbox_id)
    return {"sandbox_id": sandbox_id, "status": "destroyed"}
