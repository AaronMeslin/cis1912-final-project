"""
Snapshot creation and loading for workspace trees.

TODO:
- Define SnapshotId type (e.g. ULID or content hash of manifest).
- Walk workspace root; record regular files, dirs, symlinks; optional .git handling.
- Persist manifest + blobs to a local store (e.g. .saep/snapshots/<id>/).
- Support exclude globs (node_modules, .venv) via config file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SnapshotHandle:
    """Reference to a captured snapshot (stub)."""

    snapshot_id: str
    root: Path
    store_path: Path


def create_snapshot(root: Path, store_dir: Optional[Path] = None) -> SnapshotHandle:
    """
    Capture the directory tree under ``root`` into ``store_dir``.

    TODO: Implement directory walk, hashing, and manifest write.
    """
    _ = store_dir
    raise NotImplementedError("TODO: implement create_snapshot")


def load_snapshot(snapshot_id: str, store_dir: Path) -> SnapshotHandle:
    """
    Load an existing snapshot handle from the store.

    TODO: Validate manifest exists; resolve paths.
    """
    _ = snapshot_id
    raise NotImplementedError("TODO: implement load_snapshot")
