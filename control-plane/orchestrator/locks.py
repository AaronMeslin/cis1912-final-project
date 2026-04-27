from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Iterator


class SandboxBusy(RuntimeError):
    """Raised when a sandbox already has a running command."""


class SandboxExecLocks:
    """In-process per-sandbox locks for serialized command execution."""

    def __init__(self) -> None:
        self._guard = Lock()
        self._locks: dict[str, Lock] = {}

    def acquire_nowait(self, sandbox_id: str) -> bool:
        """Try to acquire a sandbox lock without blocking."""
        return self._lock_for(sandbox_id).acquire(blocking=False)

    def release(self, sandbox_id: str) -> None:
        """Release a sandbox lock previously acquired by acquire_nowait."""
        self._lock_for(sandbox_id).release()

    @contextmanager
    def acquire(self, sandbox_id: str) -> Iterator[None]:
        """Acquire one sandbox lock without waiting, or raise SandboxBusy."""
        if not self.acquire_nowait(sandbox_id):
            raise SandboxBusy(sandbox_id)
        try:
            yield
        finally:
            self.release(sandbox_id)

    def _lock_for(self, sandbox_id: str) -> Lock:
        with self._guard:
            lock = self._locks.get(sandbox_id)
            if lock is None:
                lock = Lock()
                self._locks[sandbox_id] = lock
            return lock
