from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status

from .config import load_settings
from .registry import SandboxRegistry

settings = load_settings()
registry = SandboxRegistry(settings.registry_db)


def initialize() -> None:
    """Initialize local orchestrator state on process startup."""
    registry.init_db()


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
def create_sandbox() -> None:
    """Placeholder for creating a Docker sandbox in the next phase."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"error": "not_implemented", "message": "Docker sandbox creation is not implemented yet"},
    )


@app.get("/sandbox/{sandbox_id}/health", dependencies=[Depends(require_internal_token)])
def sandbox_health(sandbox_id: str) -> None:
    """Placeholder for container health inspection in the next phase."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"error": "not_implemented", "message": f"Sandbox health is not implemented yet for {sandbox_id}"},
    )


@app.post("/sandbox/{sandbox_id}/exec", dependencies=[Depends(require_internal_token)])
def exec_sandbox(sandbox_id: str) -> None:
    """Placeholder for SSE command execution in the next phase."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"error": "not_implemented", "message": f"Sandbox exec is not implemented yet for {sandbox_id}"},
    )


@app.delete("/sandbox/{sandbox_id}", dependencies=[Depends(require_internal_token)])
def delete_sandbox(sandbox_id: str) -> None:
    """Placeholder for Docker sandbox deletion in the next phase."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"error": "not_implemented", "message": f"Sandbox deletion is not implemented yet for {sandbox_id}"},
    )
