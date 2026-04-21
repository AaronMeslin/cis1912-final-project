"""
Diff engine: compare a snapshot to the live workspace.

TODO:
- Walk both trees; classify paths as created, modified, deleted.
- For files: compare size + content hash or mtime policy (content preferred).
- For symlinks: compare target path; flag broken links.
- Include dotfiles and hidden dirs when snapshot did (configurable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List

from .snapshot import SnapshotHandle


class ChangeKind(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class TreeChange:
    """One path-level change between snapshot and live tree."""

    path: Path
    kind: ChangeKind
    # TODO: add symlink_target_before/after, mode bits, optional content hashes
    detail: str = ""


@dataclass
class DiffResult:
    """Structured diff output."""

    changes: List[TreeChange] = field(default_factory=list)


def diff_against_snapshot(handle: SnapshotHandle, live_root: Path) -> DiffResult:
    """
    Compute differences between ``handle`` and the current tree at ``live_root``.

    TODO: Implement comparison using manifest from SnapshotHandle.
    """
    _ = live_root
    raise NotImplementedError("TODO: implement diff_against_snapshot")
