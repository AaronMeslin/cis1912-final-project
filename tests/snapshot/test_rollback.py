from pathlib import Path
import stat

from snapshot.diff import diff_against_snapshot
from snapshot.rollback import rollback_to_snapshot
from snapshot.snapshot import create_snapshot


def test_rollback_restores_snapshot_and_removes_created_paths(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "nested").mkdir()
    (root / "nested" / "file.txt").write_text("before", encoding="utf-8")
    (root / "delete-me.txt").write_text("original", encoding="utf-8")
    (root / ".hidden").write_text("secret", encoding="utf-8")
    (root / "target.txt").write_text("target", encoding="utf-8")
    (root / "link.txt").symlink_to("target.txt")

    handle = create_snapshot(root)

    (root / "nested" / "file.txt").write_text("after", encoding="utf-8")
    (root / "delete-me.txt").unlink()
    (root / "created.txt").write_text("created", encoding="utf-8")
    (root / "created-dir").mkdir()
    (root / "created-dir" / "extra.txt").write_text("extra", encoding="utf-8")
    (root / "link.txt").unlink()
    (root / "link.txt").write_text("not a symlink", encoding="utf-8")

    report = rollback_to_snapshot(handle, root)

    assert (root / "nested" / "file.txt").read_text(encoding="utf-8") == "before"
    assert (root / "delete-me.txt").read_text(encoding="utf-8") == "original"
    assert (root / ".hidden").read_text(encoding="utf-8") == "secret"
    assert not (root / "created.txt").exists()
    assert not (root / "created-dir").exists()
    assert (root / "link.txt").is_symlink()
    assert (root / "link.txt").readlink() == Path("target.txt")
    assert not report.errors
    assert diff_against_snapshot(handle, root).changes == []


def test_rollback_preflights_missing_blobs_before_removing_live_paths(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "tracked.txt").write_text("before", encoding="utf-8")
    handle = create_snapshot(root)
    (root / "created.txt").write_text("created", encoding="utf-8")

    blob = next((handle.store_path / "blobs").iterdir())
    blob.unlink()

    report = rollback_to_snapshot(handle, root)

    assert report.errors
    assert "missing snapshot blob" in report.errors[0]
    assert (root / "created.txt").read_text(encoding="utf-8") == "created"


def test_rollback_preflights_corrupt_blobs_before_removing_live_paths(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "tracked.txt").write_text("before", encoding="utf-8")
    handle = create_snapshot(root)
    (root / "created.txt").write_text("created", encoding="utf-8")

    blob = next((handle.store_path / "blobs").iterdir())
    blob.write_text("corrupt", encoding="utf-8")

    report = rollback_to_snapshot(handle, root)

    assert report.errors
    assert "corrupt snapshot blob" in report.errors[0]
    assert (root / "created.txt").read_text(encoding="utf-8") == "created"


def test_rollback_restores_children_before_final_readonly_directory_mode(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    readonly_dir = root / "readonly"
    readonly_dir.mkdir()
    (readonly_dir / "file.txt").write_text("before", encoding="utf-8")
    readonly_dir.chmod(0o555)
    handle = create_snapshot(root)

    readonly_dir.chmod(0o755)
    (readonly_dir / "file.txt").unlink()

    report = rollback_to_snapshot(handle, root)

    assert not report.errors
    assert (readonly_dir / "file.txt").read_text(encoding="utf-8") == "before"
    assert stat.S_IMODE(readonly_dir.stat().st_mode) == 0o555
