import os
import json
import stat
from pathlib import Path

from snapshot.snapshot import create_snapshot, load_snapshot


def test_create_snapshot_captures_files_dotfiles_modes_and_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "nested").mkdir()
    (root / "nested" / "file.txt").write_text("hello", encoding="utf-8")
    (root / ".hidden").write_text("secret", encoding="utf-8")
    script = root / "run.sh"
    script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    (root / "link.txt").symlink_to("nested/file.txt")

    handle = create_snapshot(root)
    loaded = load_snapshot(handle.snapshot_id, handle.store_path.parent.parent)

    assert loaded.snapshot_id == handle.snapshot_id
    assert loaded.root == root.resolve()

    manifest = loaded.manifest
    assert manifest["entries"]["nested/file.txt"]["type"] == "file"
    assert manifest["entries"]["nested/file.txt"]["sha256"]
    assert manifest["entries"][".hidden"]["type"] == "file"
    assert manifest["entries"]["run.sh"]["mode"] & stat.S_IXUSR
    assert manifest["entries"]["link.txt"] == {
        "type": "symlink",
        "target": "nested/file.txt",
        "mode": os.lstat(root / "link.txt").st_mode,
    }


def test_create_snapshot_excludes_store_and_git_directory(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "keep.txt").write_text("keep", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    handle = create_snapshot(root)

    entries = handle.manifest["entries"]
    assert "keep.txt" in entries
    assert ".git/HEAD" not in entries
    assert not any(path.startswith(".saep/") for path in entries)


def test_load_snapshot_rejects_manifest_paths_outside_root(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    snapshot_dir = store_dir / "snapshots" / "bad"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "snapshot_id": "bad",
                "root": (tmp_path / "workspace").as_posix(),
                "entries": {
                    "../outside.txt": {"type": "file", "sha256": "abc", "size": 1, "mode": 0},
                    "/absolute.txt": {"type": "file", "sha256": "abc", "size": 1, "mode": 0},
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_snapshot("bad", store_dir)
    except ValueError as exc:
        assert "Invalid snapshot path" in str(exc)
    else:
        raise AssertionError("load_snapshot accepted an unsafe manifest path")


def test_load_snapshot_rejects_manifest_blob_paths(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    snapshot_dir = store_dir / "snapshots" / "bad-blob"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "snapshot_id": "bad-blob",
                "root": (tmp_path / "workspace").as_posix(),
                "entries": {
                    "file.txt": {"type": "file", "sha256": "../outside", "size": 1, "mode": 0},
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_snapshot("bad-blob", store_dir)
    except ValueError as exc:
        assert "Invalid snapshot blob digest" in str(exc)
    else:
        raise AssertionError("load_snapshot accepted an unsafe blob digest")


def test_load_snapshot_rejects_malformed_entries(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    snapshot_dir = store_dir / "snapshots" / "bad-entry"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "snapshot_id": "bad-entry",
                "root": (tmp_path / "workspace").as_posix(),
                "entries": {
                    "file.txt": {"type": "unknown", "mode": "not-int"},
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_snapshot("bad-entry", store_dir)
    except ValueError as exc:
        assert "Invalid snapshot entry type" in str(exc)
    else:
        raise AssertionError("load_snapshot accepted a malformed entry")


def test_load_snapshot_rejects_entries_in_excluded_roots(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    snapshot_dir = store_dir / "snapshots" / "excluded-root"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "snapshot_id": "excluded-root",
                "root": (tmp_path / "workspace").as_posix(),
                "entries": {
                    ".git/config": {"type": "file", "sha256": "a" * 64, "size": 1, "mode": 0},
                    ".saep/state.json": {"type": "file", "sha256": "b" * 64, "size": 1, "mode": 0},
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_snapshot("excluded-root", store_dir)
    except ValueError as exc:
        assert "Invalid snapshot path" in str(exc)
    else:
        raise AssertionError("load_snapshot accepted an excluded-root entry")
