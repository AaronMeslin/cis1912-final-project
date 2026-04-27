from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for registry records."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SandboxRecord:
    """One row in the SQLite sandbox registry."""

    id: str
    container_id: str
    container_name: str
    status: str
    image: str
    workspace_path: str
    created_at: str
    updated_at: str


class SandboxRegistry:
    """Small SQLite wrapper for sandbox metadata.

    Docker remains the source of truth for actual containers. This registry
    tracks the IDs and paths needed to find and clean up those containers.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def init_db(self) -> None:
        """Create the registry database and table if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sandboxes (
                    id TEXT PRIMARY KEY,
                    container_id TEXT NOT NULL,
                    container_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    image TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def insert_sandbox(
        self,
        sandbox_id: str,
        container_id: str,
        container_name: str,
        status: str,
        image: str,
        workspace_path: str,
    ) -> SandboxRecord:
        """Insert a new sandbox row and return the stored record."""
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sandboxes (
                    id, container_id, container_name, status, image, workspace_path, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sandbox_id, container_id, container_name, status, image, workspace_path, now, now),
            )
        record = self.get_sandbox(sandbox_id)
        if record is None:
            raise RuntimeError(f"failed to insert sandbox {sandbox_id}")
        return record

    def get_sandbox(self, sandbox_id: str) -> SandboxRecord | None:
        """Look up one sandbox by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sandboxes WHERE id = ?",
                (sandbox_id,),
            ).fetchone()
        return _record_from_row(row) if row else None

    def list_sandboxes(self) -> list[SandboxRecord]:
        """Return all sandbox records in creation order."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM sandboxes ORDER BY created_at ASC").fetchall()
        return [_record_from_row(row) for row in rows]

    def update_status(self, sandbox_id: str, status: str) -> bool:
        """Update a sandbox status, returning whether a row was changed."""
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE sandboxes SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), sandbox_id),
            )
        return result.rowcount > 0

    def delete_sandbox(self, sandbox_id: str) -> bool:
        """Delete a sandbox row, returning whether a row was removed."""
        with self._connect() as conn:
            result = conn.execute("DELETE FROM sandboxes WHERE id = ?", (sandbox_id,))
        return result.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection configured for named-column access."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _record_from_row(row: sqlite3.Row) -> SandboxRecord:
    """Convert a SQLite row into the typed registry dataclass."""
    return SandboxRecord(
        id=row["id"],
        container_id=row["container_id"],
        container_name=row["container_name"],
        status=row["status"],
        image=row["image"],
        workspace_path=row["workspace_path"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
