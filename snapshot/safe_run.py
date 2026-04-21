#!/usr/bin/env python3
"""
CLI entrypoint for safe execution with snapshot / diff / rollback.

Intended commands (stubs):
  safe-run <command>   — snapshot, run subprocess, record snapshot id for undo
  safe-run diff        — show changes since last snapshot
  safe-run undo        — rollback to last snapshot

TODO:
- Persist last SnapshotHandle in .saep/state.json (or env SAEP_STATE_DIR).
- Parse <command> as shell line or argv remainder; use subprocess.run with timeout.
- Integrate snapshot.create_snapshot, diff.diff_against_snapshot, rollback.rollback_to_snapshot.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_run(argv: list[str]) -> int:
    """TODO: create snapshot, run command, store snapshot id, return process exit code."""
    _ = argv
    raise NotImplementedError("TODO: implement safe-run <command>")


def _cmd_diff(_args: argparse.Namespace) -> int:
    """TODO: load last snapshot handle and print diff."""
    raise NotImplementedError("TODO: implement safe-run diff")


def _cmd_undo(_args: argparse.Namespace) -> int:
    """TODO: rollback using last snapshot id."""
    raise NotImplementedError("TODO: implement safe-run undo")


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

    # `safe_run.py diff` / `safe_run.py undo` when invoked as script
    if argv[0] == "diff":
        return _cmd_diff(argparse.Namespace())
    if argv[0] == "undo":
        return _cmd_undo(argparse.Namespace())

    # Default: treat as `safe-run <command>` (everything after script name)
    return _cmd_run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
