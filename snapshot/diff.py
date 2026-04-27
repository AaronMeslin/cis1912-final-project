"""Diff engine: compare a snapshot to the live workspace."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, List

from .snapshot import SnapshotHandle, _is_excluded, _sha256_file


class ChangeKind(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class TreeChange:
    """One path-level change between snapshot and live tree."""

    path: Path
    kind: ChangeKind
    detail: str = ""


@dataclass
class DiffResult:
    """Structured diff output."""

    changes: List[TreeChange] = field(default_factory=list)


def diff_against_snapshot(handle: SnapshotHandle, live_root: Path) -> DiffResult:
    """Compute differences between ``handle`` and the current tree at ``live_root``."""
    before = handle.manifest["entries"]
    after = _scan_live_tree(live_root.resolve())

    changes: list[TreeChange] = []
    for key in sorted(before.keys() - after.keys()):
        changes.append(TreeChange(path=Path(key), kind=ChangeKind.DELETED))

    for key in sorted(after.keys() - before.keys()):
        changes.append(TreeChange(path=Path(key), kind=ChangeKind.CREATED))

    for key in sorted(before.keys() & after.keys()):
        detail = _change_detail(before[key], after[key])
        if detail:
            changes.append(TreeChange(path=Path(key), kind=ChangeKind.MODIFIED, detail=detail))

    return DiffResult(changes=changes)


def _scan_live_tree(root: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative_path = path.relative_to(root)
        if _is_excluded(relative_path):
            continue

        key = relative_path.as_posix()
        stat_result = os.lstat(path)
        mode = stat_result.st_mode
        if path.is_symlink():
            entries[key] = {
                "type": "symlink",
                "target": os.readlink(path),
                "mode": mode,
            }
        elif path.is_dir():
            entries[key] = {
                "type": "directory",
                "mode": mode,
            }
        elif path.is_file():
            entries[key] = {
                "type": "file",
                "sha256": _sha256_file(path),
                "size": stat_result.st_size,
                "mode": mode,
            }
    return entries


def _change_detail(before: dict[str, Any], after: dict[str, Any]) -> str:
    if before["type"] != after["type"]:
        return f"type {before['type']} -> {after['type']}"

    entry_type = before["type"]
    if entry_type == "file":
        if before["sha256"] != after["sha256"]:
            return "content changed"
        if before["mode"] != after["mode"]:
            return "mode changed"
    elif entry_type == "symlink":
        if before["target"] != after["target"]:
            return f"target {before['target']} -> {after['target']}"
    elif entry_type == "directory" and before["mode"] != after["mode"]:
        return "mode changed"

    return ""
