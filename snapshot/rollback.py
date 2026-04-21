"""
Rollback: restore workspace from a snapshot.

TODO:
- Restore files and symlinks from snapshot blobs; delete paths that did not exist in snapshot.
- Optional safety: move current tree aside to a quarantine directory before restore.
- Return report of actions for observability / audit log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .snapshot import SnapshotHandle


@dataclass
class RollbackReport:
    """Summary of rollback operations (stub)."""

    restored_paths: List[Path] = field(default_factory=list)
    removed_paths: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def rollback_to_snapshot(handle: SnapshotHandle, live_root: Path) -> RollbackReport:
    """
    Restore ``live_root`` to match the snapshot referenced by ``handle``.

    TODO: Implement transactional restore; handle permission errors clearly.
    """
    _ = live_root
    raise NotImplementedError("TODO: implement rollback_to_snapshot")
