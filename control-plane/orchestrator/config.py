from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    """Read an integer environment variable with a simple default fallback."""
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the local orchestrator process."""

    host: str
    port: int
    sandbox_image: str
    registry_db: Path
    workspaces_dir: Path
    internal_token: str | None
    exec_timeout_seconds: int


def load_settings() -> Settings:
    """Load orchestrator settings from environment variables."""
    return Settings(
        host=os.getenv("SAEP_ORCHESTRATOR_HOST", "127.0.0.1"),
        port=_int_env("SAEP_ORCHESTRATOR_PORT", 9999),
        sandbox_image=os.getenv("SAEP_SANDBOX_IMAGE", "saep-sandbox:local"),
        registry_db=Path(os.getenv("SAEP_REGISTRY_DB", ".saep-orchestrator/registry.sqlite3")),
        workspaces_dir=Path(os.getenv("SAEP_WORKSPACES_DIR", ".saep-orchestrator/workspaces")),
        internal_token=os.getenv("SAEP_INTERNAL_TOKEN") or None,
        exec_timeout_seconds=_int_env("SAEP_EXEC_TIMEOUT_SECONDS", 300),
    )
