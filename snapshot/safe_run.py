#!/usr/bin/env python3
"""CLI entrypoint for safe execution with snapshot / diff / rollback."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from .diff import diff_against_snapshot
from .rollback import rollback_to_snapshot
from .snapshot import SNAPSHOT_STORE_DIR, create_snapshot, load_snapshot


def _store_dir(root: Path) -> Path:
    return root / SNAPSHOT_STORE_DIR


def _state_path(root: Path) -> Path:
    return _store_dir(root) / "state.json"


def _state_payload(root: Path, snapshot_id: str, store_dir: Path) -> dict[str, str]:
    return {
        "last_snapshot_id": snapshot_id,
        "root": root.resolve().as_posix(),
        "store_dir": store_dir.absolute().as_posix(),
    }


def _write_state_file(state_file: Path, payload: dict[str, str]) -> None:
    if state_file.is_symlink() or (state_file.exists() and not state_file.is_file()):
        state_file.unlink()
    state_file.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_state(root: Path, snapshot_id: str) -> None:
    _write_state_file(_state_path(root), _state_payload(root, snapshot_id, _store_dir(root)))


def _read_state(root: Path) -> dict[str, str]:
    state_file = _state_path(root)
    if not state_file.is_file():
        raise FileNotFoundError(f"No safe-run state found at {state_file}")
    return json.loads(state_file.read_text(encoding="utf-8"))


def _load_last_snapshot(root: Path):
    state = _read_state(root)
    expected_root = root.resolve()
    if Path(state["root"]) != expected_root:
        raise ValueError(f"State root {state['root']} does not match current root {expected_root}")
    handle = load_snapshot(state["last_snapshot_id"], Path(state["store_dir"]))
    if handle.root != expected_root:
        raise ValueError(f"Snapshot root {handle.root} does not match current root {expected_root}")
    return handle


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _persist_snapshot(handle, store_dir: Path, root: Path) -> None:
    new_store = store_dir.with_name(f"{store_dir.name}.new-{handle.snapshot_id}")
    backup_store = store_dir.with_name(f"{store_dir.name}.backup-{uuid.uuid4().hex}")
    _remove_path(new_store)
    new_store.mkdir(parents=True)

    destination = new_store / "snapshots" / handle.snapshot_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(handle.store_path, destination)
        _write_state_file(
            new_store / "state.json",
            _state_payload(root, handle.snapshot_id, store_dir),
        )
        had_previous_store = store_dir.exists() or store_dir.is_symlink()
        if had_previous_store:
            store_dir.rename(backup_store)
        try:
            new_store.rename(store_dir)
        except OSError:
            if had_previous_store:
                backup_store.rename(store_dir)
            raise
        _remove_path(backup_store)
    except Exception:
        _remove_path(new_store)
        raise


def _cmd_run(argv: list[str]) -> int:
    """Create a snapshot, run a command, store snapshot id, return process exit code."""
    cmd = argv[1:] if argv and argv[0] == "run" else argv
    if not cmd:
        print("safe-run: missing command", file=sys.stderr)
        return 2

    root = Path.cwd()
    temp_store = Path(tempfile.mkdtemp(prefix="saep-snapshot-"))
    try:
        handle = create_snapshot(root, temp_store)
        completed = subprocess.run(cmd, check=False)
        _persist_snapshot(handle, _store_dir(root), root)
        return completed.returncode
    finally:
        shutil.rmtree(temp_store, ignore_errors=True)


def _cmd_diff(_args: argparse.Namespace) -> int:
    """Load last snapshot handle and print diff."""
    root = Path.cwd()
    try:
        handle = _load_last_snapshot(root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"safe-run: {exc}", file=sys.stderr)
        return 2

    result = diff_against_snapshot(handle, root)
    if not result.changes:
        print("No changes")
        return 0

    for change in result.changes:
        detail = f" ({change.detail})" if change.detail else ""
        print(f"{change.kind.value} {change.path.as_posix()}{detail}")
    return 1


def _cmd_undo(_args: argparse.Namespace) -> int:
    """Rollback using last snapshot id."""
    root = Path.cwd()
    try:
        handle = _load_last_snapshot(root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"safe-run: {exc}", file=sys.stderr)
        return 2

    report = rollback_to_snapshot(handle, root)
    for path in report.removed_paths:
        print(f"removed {path.as_posix()}")
    for path in report.restored_paths:
        print(f"restored {path.as_posix()}")
    for error in report.errors:
        print(f"error {error}", file=sys.stderr)
    return 1 if report.errors else 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="safe-run")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run a command under snapshot (alias: default)")
    p_run.add_argument("cmd", nargs=argparse.REMAINDER, help="Command and arguments")

    sub.add_parser("diff", help="Diff workspace against last snapshot")
    sub.add_parser("undo", help="Rollback workspace to last snapshot")

    # Support `safe-run diff` without subcommand name: detect first token
    if argv and argv[0] in ("diff", "undo"):
        cmd = argv[0]
        rest = argv[1:]
        if cmd == "diff":
            return _cmd_diff(argparse.Namespace())
        if cmd == "undo":
            return _cmd_undo(argparse.Namespace())
        _ = rest

    if not argv:
        parser.print_help()
        return 2

    if argv[0] in ("-h", "--help"):
        parser.print_help()
        return 0

    if argv[0] == "run" and len(argv) > 1 and argv[1] in ("-h", "--help"):
        p_run.print_help()
        return 0

    if argv[0] in ("diff", "undo"):
        return _cmd_diff(argparse.Namespace()) if argv[0] == "diff" else _cmd_undo(argparse.Namespace())

    # Default: treat as `safe-run <command>` (everything after script name)
    return _cmd_run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
