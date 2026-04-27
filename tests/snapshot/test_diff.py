from pathlib import Path

from snapshot.diff import ChangeKind, diff_against_snapshot
from snapshot.snapshot import create_snapshot


def test_diff_reports_created_modified_deleted_and_symlink_changes(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "keep.txt").write_text("before", encoding="utf-8")
    (root / "delete.txt").write_text("remove me", encoding="utf-8")
    (root / ".hidden").write_text("old", encoding="utf-8")
    (root / "target-a.txt").write_text("a", encoding="utf-8")
    (root / "target-b.txt").write_text("b", encoding="utf-8")
    (root / "link.txt").symlink_to("target-a.txt")

    handle = create_snapshot(root)

    (root / "keep.txt").write_text("after", encoding="utf-8")
    (root / "delete.txt").unlink()
    (root / "created.txt").write_text("new", encoding="utf-8")
    (root / ".hidden").write_text("new hidden", encoding="utf-8")
    (root / "link.txt").unlink()
    (root / "link.txt").symlink_to("target-b.txt")

    result = diff_against_snapshot(handle, root)

    changes = {(change.path.as_posix(), change.kind) for change in result.changes}
    assert ("keep.txt", ChangeKind.MODIFIED) in changes
    assert ("delete.txt", ChangeKind.DELETED) in changes
    assert ("created.txt", ChangeKind.CREATED) in changes
    assert (".hidden", ChangeKind.MODIFIED) in changes
    assert ("link.txt", ChangeKind.MODIFIED) in changes


def test_diff_has_no_changes_for_unchanged_tree(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "file.txt").write_text("same", encoding="utf-8")

    handle = create_snapshot(root)

    assert diff_against_snapshot(handle, root).changes == []
