from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard JSON error payload used by orchestrator endpoints."""

    error: str
    message: str


class CreateResponse(BaseModel):
    """Response shape for a successfully created sandbox."""

    sandbox_id: str
    container_id: str
    status: str
    created_at: str


class HealthMetrics(BaseModel):
    """Resource metrics returned by the sandbox health endpoint."""

    cpu_percent: float | None = None
    memory_bytes: int | None = None


class HealthResponse(BaseModel):
    """Health response for an existing sandbox."""

    sandbox_id: str
    healthy: bool
    status: str
    created_at: str
    metrics: HealthMetrics


class ExecRequest(BaseModel):
    """Request body for running a command inside a sandbox."""

    command: list[str] = Field(min_length=1)
    timeout: int = Field(default=300, ge=1)
