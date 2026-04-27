import json
import subprocess
import sys
from pathlib import Path

import pytest

import snapshot.safe_run as safe_run
from snapshot.safe_run import main
from snapshot.snapshot import create_snapshot


def test_safe_run_run_diff_and_undo_round_trip(tmp_path: Path, capsys) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    command = [
        "run",
        sys.executable,
        "-c",
        "from pathlib import Path; Path('hello.txt').write_text('hi', encoding='utf-8')",
    ]

    cwd = Path.cwd()
    try:
        import os

        os.chdir(root)
        assert main(command) == 0

        state = json.loads((root / ".saep" / "state.json").read_text(encoding="utf-8"))
        assert state["last_snapshot_id"]

        assert main(["diff"]) == 1
        diff_output = capsys.readouterr().out
        assert "created hello.txt" in diff_output

        assert main(["undo"]) == 0
        undo_output = capsys.readouterr().out
        assert "removed" in undo_output
        assert not (root / "hello.txt").exists()

        assert main(["diff"]) == 0
        clean_output = capsys.readouterr().out
        assert "No changes" in clean_output
    finally:
        os.chdir(cwd)


def test_safe_run_returns_subprocess_exit_code(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()

    cwd = Path.cwd()
    try:
        import os

        os.chdir(root)
        assert main(["run", sys.executable, "-c", "raise SystemExit(7)"]) == 7
    finally:
        os.chdir(cwd)


def test_safe_run_preserves_snapshot_when_command_deletes_state_dir(tmp_path: Path, capsys) -> None:
    root = tmp_path / "workspace"
    root.mkdir()

    cwd = Path.cwd()
    try:
        import os

        os.chdir(root)
        assert (
            main(
                [
                    "run",
                    sys.executable,
                    "-c",
                    (
                        "import shutil; "
                        "from pathlib import Path; "
                        "shutil.rmtree('.saep', ignore_errors=True); "
                        "Path('hello.txt').write_text('hi', encoding='utf-8')"
                    ),
                ]
            )
            == 0
        )
        assert main(["diff"]) == 1
        assert "created hello.txt" in capsys.readouterr().out
    finally:
        os.chdir(cwd)


def test_safe_run_does_not_follow_state_dir_symlink_created_by_command(tmp_path: Path, capsys) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    cwd = Path.cwd()
    try:
        import os

        os.chdir(root)
        assert (
            main(
                [
                    "run",
                    sys.executable,
                    "-c",
                    (
                        "import os; "
                        "from pathlib import Path; "
                        "Path('.saep').symlink_to('../outside', target_is_directory=True); "
                        "Path('hello.txt').write_text('hi', encoding='utf-8')"
                    ),
                ]
            )
            == 0
        )
        assert not any(outside.iterdir())
        assert (root / ".saep").is_dir()
        assert not (root / ".saep").is_symlink()
        assert main(["diff"]) == 1
        assert "created hello.txt" in capsys.readouterr().out
    finally:
        os.chdir(cwd)


def test_safe_run_does_not_follow_nested_state_symlinks_created_by_command(tmp_path: Path, capsys) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    cwd = Path.cwd()
    try:
        import os

        os.chdir(root)
        assert (
            main(
                [
                    "run",
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path; "
                        "Path('.saep').mkdir(); "
                        "Path('.saep/state.json').symlink_to('../outside/state.json'); "
                        "Path('.saep/snapshots').symlink_to('../outside', target_is_directory=True); "
                        "Path('hello.txt').write_text('hi', encoding='utf-8')"
                    ),
                ]
            )
            == 0
        )
        assert not any(outside.iterdir())
        assert (root / ".saep" / "state.json").is_file()
        assert not (root / ".saep" / "state.json").is_symlink()
        assert (root / ".saep" / "snapshots").is_dir()
        assert not (root / ".saep" / "snapshots").is_symlink()
        assert main(["diff"]) == 1
        assert "created hello.txt" in capsys.readouterr().out
    finally:
        os.chdir(cwd)


def test_module_cli_supports_default_command_diff_and_undo(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    repo_root = Path(__file__).resolve().parents[2]

    run_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "snapshot.safe_run",
            sys.executable,
            "-c",
            "from pathlib import Path; Path('hello.txt').write_text('hi', encoding='utf-8')",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert run_result.returncode == 0

    diff_result = subprocess.run(
        [sys.executable, "-m", "snapshot.safe_run", "diff"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert diff_result.returncode == 1
    assert "created hello.txt" in diff_result.stdout

    undo_result = subprocess.run(
        [sys.executable, "-m", "snapshot.safe_run", "undo"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(repo_root)},
    )
    assert undo_result.returncode == 0
    assert not (root / "hello.txt").exists()


def test_safe_run_help_prints_usage(capsys) -> None:
    assert main(["--help"]) == 0
    assert "usage: safe-run" in capsys.readouterr().out


def test_safe_run_run_help_prints_subcommand_usage(capsys) -> None:
    assert main(["run", "--help"]) == 0
    assert "usage: safe-run run" in capsys.readouterr().out


def test_persist_snapshot_keeps_previous_state_when_publish_fails(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    store_dir = root / ".saep"
    store_dir.mkdir()
    (store_dir / "state.json").write_text("old-state", encoding="utf-8")
    (root / "file.txt").write_text("before", encoding="utf-8")
    handle = create_snapshot(root, tmp_path / "temp-store")

    def fail_copytree(*args, **kwargs):
        raise OSError("copy failed")

    monkeypatch.setattr(safe_run.shutil, "copytree", fail_copytree)

    with pytest.raises(OSError, match="copy failed"):
        safe_run._persist_snapshot(handle, store_dir, root)

    assert (store_dir / "state.json").read_text(encoding="utf-8") == "old-state"
