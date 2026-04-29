from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import json
from pathlib import Path
import shutil
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from .config import load_settings
from .docker_client import (
    DockerSandboxClient,
    ExecExit,
    ExecOutput,
    SandboxContainerNotFound,
    SandboxExecTimedOut,
    SandboxImageNotFound,
)
from .locks import SandboxExecLocks
from .models import CreateResponse, ExecRequest, HealthMetrics, HealthResponse
from .registry import SandboxRegistry

settings = load_settings()
registry = SandboxRegistry(settings.registry_db)
docker_client: DockerSandboxClient | None = None
exec_locks = SandboxExecLocks()


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
        seed_workspace(workspace_path)
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


def seed_workspace(workspace_path: Path) -> None:
    """Optionally copy a local seed directory into a new sandbox workspace."""
    if settings.workspace_seed_dir is None:
        return
    if not settings.workspace_seed_dir.is_dir():
        raise RuntimeError(f"workspace seed directory does not exist: {settings.workspace_seed_dir}")
    workspace_path.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        settings.workspace_seed_dir,
        workspace_path,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".saep",
            ".venv",
            "__pycache__",
            "node_modules",
            "saep.egg-info",
        ),
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
def exec_sandbox(
    sandbox_id: str,
    request: ExecRequest,
    client: DockerSandboxClient = Depends(get_docker_client),
) -> StreamingResponse:
    """Run a command inside a sandbox and stream output as SSE."""
    record = registry.get_sandbox(sandbox_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Sandbox not found: {sandbox_id}"},
        )
    if not _try_acquire_exec_lock(sandbox_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "sandbox_busy", "message": "Another command is already running in this sandbox"},
        )
    return StreamingResponse(
        _exec_stream(sandbox_id, record.container_id, request, client),
        media_type="text/event-stream",
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


def _try_acquire_exec_lock(sandbox_id: str) -> bool:
    """Try to reserve a sandbox for command execution."""
    return exec_locks.acquire_nowait(sandbox_id)


def _release_exec_lock(sandbox_id: str) -> None:
    """Release a lock reserved by _try_acquire_exec_lock."""
    exec_locks.release(sandbox_id)


def _exec_stream(
    sandbox_id: str,
    container_id: str,
    request: ExecRequest,
    client: DockerSandboxClient,
):
    """Yield SSE messages while holding the sandbox exec lock."""
    try:
        try:
            for event in client.exec_command(container_id, request.command, request.timeout):
                if isinstance(event, ExecOutput):
                    yield _sse("output", {"stream": event.stream, "line": event.data})
                elif isinstance(event, ExecExit):
                    yield _sse("exit", {"code": event.code})
        except SandboxContainerNotFound:
            yield _sse("error", {"error": "container_not_found", "message": "Sandbox container not found"})
            yield _sse("exit", {"code": 127})
        except SandboxExecTimedOut as exc:
            yield _sse("error", {"error": "command_timed_out", "message": str(exc)})
            yield _sse("exit", {"code": 124})
        except Exception as exc:
            yield _sse("error", {"error": "exec_failed", "message": str(exc)})
            yield _sse("exit", {"code": 1})
    finally:
        _release_exec_lock(sandbox_id)


def _sse(event: str, payload: dict) -> str:
    """Format one server-sent event frame."""
    return f"event: {event}\ndata: {json.dumps(payload, sort_keys=True)}\n\n"
