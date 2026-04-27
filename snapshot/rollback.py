"""Rollback: restore workspace from a snapshot."""

from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .diff import _scan_live_tree
from .snapshot import SnapshotHandle, _blobs_dir, _sha256_file, validate_manifest


@dataclass
class RollbackReport:
    """Summary of rollback operations (stub)."""

    restored_paths: List[Path] = field(default_factory=list)
    removed_paths: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def rollback_to_snapshot(handle: SnapshotHandle, live_root: Path) -> RollbackReport:
    """Restore ``live_root`` to match the snapshot referenced by ``handle``."""
    root = live_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    report = RollbackReport()
    try:
        _preflight_snapshot(handle)
    except (OSError, ValueError) as exc:
        report.errors.append(str(exc))
        return report

    before = handle.manifest["entries"]
    after = _scan_live_tree(root)

    for key in sorted(after.keys() - before.keys(), key=lambda item: item.count("/"), reverse=True):
        path = root / key
        try:
            _remove_path(path)
            report.removed_paths.append(Path(key))
        except OSError as exc:
            report.errors.append(f"failed to remove {key}: {exc}")

    directory_entries = {
        key: entry for key, entry in before.items() if entry["type"] == "directory"
    }
    non_directory_entries = {
        key: entry for key, entry in before.items() if entry["type"] != "directory"
    }

    for key, entry in sorted(directory_entries.items(), key=lambda item: (item[0].count("/"), item[0])):
        path = root / key
        try:
            _restore_directory(path, entry, temporary_writable=True)
            report.restored_paths.append(Path(key))
        except OSError as exc:
            report.errors.append(f"failed to restore {key}: {exc}")

    for key, entry in sorted(non_directory_entries.items(), key=lambda item: (item[0].count("/"), item[0])):
        path = root / key
        try:
            _restore_entry(path, entry, handle)
            report.restored_paths.append(Path(key))
        except OSError as exc:
            report.errors.append(f"failed to restore {key}: {exc}")

    for key, entry in sorted(directory_entries.items(), key=lambda item: (item[0].count("/"), item[0]), reverse=True):
        path = root / key
        try:
            os.chmod(path, entry["mode"])
        except OSError as exc:
            report.errors.append(f"failed to restore mode for {key}: {exc}")

    return report


def _preflight_snapshot(handle: SnapshotHandle) -> None:
    validate_manifest(handle.manifest)
    blobs_dir = _blobs_dir(handle.store_path)
    for key, entry in handle.manifest["entries"].items():
        if entry["type"] != "file":
            continue
        blob = blobs_dir / entry["sha256"]
        if not blob.is_file():
            raise FileNotFoundError(f"missing snapshot blob for {key}: {blob}")
        if _sha256_file(blob) != entry["sha256"]:
            raise ValueError(f"corrupt snapshot blob for {key}: {blob}")


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _clear_existing_path(path: Path, desired_type: str) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if desired_type == "directory" and path.is_dir() and not path.is_symlink():
        return
    _remove_path(path)


def _restore_entry(path: Path, entry: dict, handle: SnapshotHandle) -> None:
    entry_type = entry["type"]
    _clear_existing_path(path, entry_type)
    path.parent.mkdir(parents=True, exist_ok=True)

    if entry_type == "directory":
        _restore_directory(path, entry, temporary_writable=False)
        return

    if entry_type == "symlink":
        path.symlink_to(entry["target"])
        return

    if entry_type == "file":
        source = _blobs_dir(handle.store_path) / entry["sha256"]
        shutil.copy2(source, path, follow_symlinks=False)
        os.chmod(path, entry["mode"])
        return

    raise ValueError(f"Unsupported snapshot entry type: {entry_type}")


def _restore_directory(path: Path, entry: dict, temporary_writable: bool) -> None:
    _clear_existing_path(path, "directory")
    path.mkdir(parents=True, exist_ok=True)
    mode = entry["mode"]
    if temporary_writable:
        mode |= stat.S_IWUSR | stat.S_IXUSR
    os.chmod(path, mode)
