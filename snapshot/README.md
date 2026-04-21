# `snapshot/` — Snapshot, diff, rollback engine

## What this component is

This package implements the **safety layer** between “agent ran a command” and “the repo on disk changed.” Before running a command, we capture a **snapshot** of the working directory (or a configured root). Afterward we can **diff** against that snapshot (created, modified, deleted entries, including symlinks and dotfiles) and **rollback** to restore the tree.

The CLI entrypoint is [`safe_run.py`](safe_run.py), intended to be exposed as `safe-run` once packaged (`pip install` or a thin shell wrapper).

## Files in this directory

| File | Role |
|------|------|
| [__init__.py](__init__.py) | Marks `snapshot` as a Python package so `python -m snapshot.safe_run` works |
| [safe_run.py](safe_run.py) | CLI: `safe-run <command>`, `safe-run diff`, `safe-run undo` |
| [snapshot.py](snapshot.py) | Create and load snapshots of a directory tree |
| [diff.py](diff.py) | Compare snapshot vs live tree; structured change list |
| [rollback.py](rollback.py) | Restore workspace from a snapshot |

## Design notes

- **Snapshot format**: likely a content-addressed store (files hashed by content) plus metadata for paths, modes, symlinks, and xattrs—**TBD** in implementation.
- **Scope**: snapshot root defaults to current working directory; must handle `.hidden` files and nested `.git` policy (often exclude `.git` from snapshots or snapshot it read-only—product decision).
- **Large binaries**: stream or hardlink; avoid loading multi-GB files into RAM; add tests for big files.
- **Symlinks**: record link target; on rollback, recreate symlink vs follow policy must be explicit.

## How `safe-run` should orchestrate (target flow)

1. Resolve workspace root and snapshot store path (env or `.saep/` directory).
2. **Before** subprocess: `create_snapshot()` → returns snapshot id.
3. Run user command subprocess; capture exit code, stdout/stderr (optional logging to observability layer).
4. On success path: user may run `safe-run diff` to review changes; `safe-run undo` restores from last snapshot id.

## Edge cases to cover in tests

- Large files, sparse files (if supported)
- Symlinks (absolute vs relative)
- Hidden files and directories
- Permission bits and executability
- Concurrent runs (lock snapshot store)

## Tasks to implement

- [ ] Define on-disk snapshot layout and versioning
- [ ] Implement `snapshot.py`: capture tree, exclude patterns, symlink metadata
- [ ] Implement `diff.py`: unified change list (create/modify/delete), symlink and dotfile handling
- [ ] Implement `rollback.py`: atomic restore where possible; backup current broken state before undo
- [ ] Wire `safe_run.py` subprocess execution with configurable timeout and env whitelist
- [ ] Add pytest suite: golden trees, large binary, symlinks, hidden files
- [ ] Document integration with Docker (snapshot runs on host volume bind-mounted into sandbox)
