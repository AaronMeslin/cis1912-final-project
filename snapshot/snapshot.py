"""Snapshot creation and loading for workspace trees."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import string
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Optional

SNAPSHOT_STORE_DIR = ".saep"
SNAPSHOT_FORMAT_VERSION = 1
_EXCLUDED_ROOT_NAMES = {SNAPSHOT_STORE_DIR, ".git"}
_HEX_DIGITS = set(string.hexdigits)
_ENTRY_TYPES = {"file", "directory", "symlink"}


@dataclass(frozen=True)
class SnapshotHandle:
    """Reference to a captured snapshot."""

    snapshot_id: str
    root: Path
    store_path: Path
    manifest: dict[str, Any]


def _default_store_dir(root: Path) -> Path:
    return root / SNAPSHOT_STORE_DIR


def _snapshots_dir(store_dir: Path) -> Path:
    return store_dir / "snapshots"


def _manifest_path(snapshot_dir: Path) -> Path:
    return snapshot_dir / "manifest.json"


def _blobs_dir(snapshot_dir: Path) -> Path:
    return snapshot_dir / "blobs"


def _is_excluded(relative_path: Path) -> bool:
    return bool(relative_path.parts) and relative_path.parts[0] in _EXCLUDED_ROOT_NAMES


def _relative_key(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_blob(source: Path, blobs_dir: Path, digest: str) -> None:
    destination = blobs_dir / digest
    if destination.exists():
        return
    shutil.copy2(source, destination, follow_symlinks=False)


def _write_manifest(snapshot_dir: Path, manifest: dict[str, Any]) -> None:
    _manifest_path(snapshot_dir).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate manifest structure that affects filesystem writes."""
    entries = manifest.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("Snapshot manifest must contain an entries object")
    for key in entries:
        validate_manifest_path(key)
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid snapshot entry for {key}: entry must be an object")
        entry_type = entry.get("type")
        if entry_type not in _ENTRY_TYPES:
            raise ValueError(f"Invalid snapshot entry type for {key}: {entry_type}")
        if not isinstance(entry.get("mode"), int):
            raise ValueError(f"Invalid snapshot mode for {key}: {entry.get('mode')}")
        if entry_type == "file":
            digest = entry.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(char not in _HEX_DIGITS for char in digest):
                raise ValueError(f"Invalid snapshot blob digest for {key}: {digest}")
            if not isinstance(entry.get("size"), int):
                raise ValueError(f"Invalid snapshot size for {key}: {entry.get('size')}")
        elif entry_type == "symlink" and not isinstance(entry.get("target"), str):
            raise ValueError(f"Invalid snapshot symlink target for {key}: {entry.get('target')}")


def validate_manifest_path(key: str) -> None:
    """Reject absolute, parent-traversing, or non-normalized manifest paths."""
    path = PurePosixPath(key)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != key
        or (path.parts and path.parts[0] in _EXCLUDED_ROOT_NAMES)
    ):
        raise ValueError(f"Invalid snapshot path: {key}")


def create_snapshot(root: Path, store_dir: Optional[Path] = None) -> SnapshotHandle:
    """Capture the directory tree under ``root`` into ``store_dir``."""
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise ValueError(f"Snapshot root must be a directory: {root}")

    resolved_store_dir = (store_dir or _default_store_dir(resolved_root)).resolve()
    snapshot_id = uuid.uuid4().hex
    snapshot_dir = _snapshots_dir(resolved_store_dir) / snapshot_id
    blobs_dir = _blobs_dir(snapshot_dir)
    blobs_dir.mkdir(parents=True, exist_ok=False)

    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(resolved_root.rglob("*"), key=lambda item: item.relative_to(resolved_root).as_posix()):
        relative_path = path.relative_to(resolved_root)
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
            digest = _sha256_file(path)
            _copy_blob(path, blobs_dir, digest)
            entries[key] = {
                "type": "file",
                "sha256": digest,
                "size": stat_result.st_size,
                "mode": mode,
            }

    manifest: dict[str, Any] = {
        "version": SNAPSHOT_FORMAT_VERSION,
        "snapshot_id": snapshot_id,
        "root": resolved_root.as_posix(),
        "entries": entries,
    }
    _write_manifest(snapshot_dir, manifest)
    return SnapshotHandle(
        snapshot_id=snapshot_id,
        root=resolved_root,
        store_path=snapshot_dir,
        manifest=manifest,
    )


def load_snapshot(snapshot_id: str, store_dir: Path) -> SnapshotHandle:
    """Load an existing snapshot handle from the store."""
    snapshot_dir = _snapshots_dir(store_dir.resolve()) / snapshot_id
    manifest_file = _manifest_path(snapshot_dir)
    if not manifest_file.is_file():
        raise FileNotFoundError(f"Snapshot manifest not found: {manifest_file}")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("snapshot_id") != snapshot_id:
        raise ValueError(f"Snapshot id mismatch in manifest: {manifest_file}")
    if manifest.get("version") != SNAPSHOT_FORMAT_VERSION:
        raise ValueError(f"Unsupported snapshot version: {manifest.get('version')}")
    validate_manifest(manifest)

    return SnapshotHandle(
        snapshot_id=snapshot_id,
        root=Path(manifest["root"]),
        store_path=snapshot_dir,
        manifest=manifest,
    )
