# `snapshot/` — Snapshot, diff, rollback engine

## What this component is

This package implements the **safety layer** between “agent ran a command” and “the repo on disk changed.” Before running a command, it captures a **snapshot** of the working directory. Afterward it can **diff** against that snapshot (created, modified, deleted entries, including symlinks and dotfiles) and **rollback** to restore the tree.

The CLI entrypoint is [`safe_run.py`](safe_run.py). Run it with `python3 -m snapshot.safe_run`, or install the package in editable mode and use `safe-run`.

## Files in this directory

| File | Role |
|------|------|
| [__init__.py](__init__.py) | Marks `snapshot` as a Python package so `python -m snapshot.safe_run` works |
| [safe_run.py](safe_run.py) | CLI: `safe-run <command>`, `safe-run diff`, `safe-run undo` |
| [snapshot.py](snapshot.py) | Create and load snapshots of a directory tree |
| [diff.py](diff.py) | Compare snapshot vs live tree; structured change list |
| [rollback.py](rollback.py) | Restore workspace from a snapshot |

## Current behavior

- **Snapshot format**: `.saep/snapshots/<snapshot_id>/manifest.json` plus content-addressed file blobs under `blobs/`.
- **Scope**: snapshot root defaults to the current working directory.
- **Exclusions**: `.saep/` and `.git/` are excluded from snapshots and rollback.
- **Files**: regular files are hashed with SHA-256 and copied into the blob store.
- **Directories**: directories are recorded so rollback can recreate missing structure.
- **Symlinks**: symlink targets are recorded and recreated as symlinks on rollback.
- **State**: `.saep/state.json` stores the last snapshot id for `diff` and `undo`.
- **Manifest validation**: loaded snapshots reject absolute paths, parent traversal, `.git/` or `.saep/` entries, malformed entry metadata, and invalid blob digests.
- **Rollback preflight**: rollback validates all manifest entries and checks file blob existence and SHA-256 integrity before mutating the workspace.
- **CLI staging**: `safe-run run` creates the pre-command snapshot in a temporary store first, then publishes it into `.saep/` after the command exits so the wrapped process cannot delete or redirect the current snapshot metadata before state is persisted.
- **Docker integration**: the sandbox image installs `safe-run`; the Docker smoke test mounts a throwaway workspace and verifies `run`, `diff`, and `undo` inside the container.

## Usage

From a workspace root:

```bash
python3 -m snapshot.safe_run run python3 -c "open('hello.txt', 'w').write('hi')"
python3 -m snapshot.safe_run diff
python3 -m snapshot.safe_run undo
```

After `pip install -e ".[dev]"`, the equivalent console command is available:

```bash
safe-run run python3 -c "open('hello.txt', 'w').write('hi')"
safe-run diff
safe-run undo
```

`diff` exits `1` when changes are present and `0` when the workspace matches the last snapshot. `undo` restores the workspace to the last snapshot.

Manual verification from a throwaway directory should look like this:

```bash
mkdir -p /tmp/saep-manual-test
cd /tmp/saep-manual-test
safe-run run python3 -c "open('hello.txt', 'w').write('hi')"
safe-run diff     # created hello.txt
safe-run undo     # removed hello.txt
```

For modification rollback:

```bash
echo "before" > file.txt
safe-run run python3 -c "open('file.txt', 'w').write('after\n')"
safe-run diff     # modified file.txt (content changed)
cat file.txt      # after
safe-run undo     # restored file.txt
cat file.txt      # before
```

## How `safe-run` orchestrates

1. Resolve workspace root and snapshot store path (env or `.saep/` directory).
2. **Before** subprocess: `create_snapshot()` records the tree in a temporary store outside the workspace.
3. Run user command subprocess and capture its exit code.
4. Copy the snapshot into `.saep/snapshots/<snapshot_id>/` and write `.saep/state.json`.
5. User may run `safe-run diff` to review changes; `safe-run undo` restores from the last snapshot id.

## Edge case behavior

The snapshot engine tracks regular files by bytes, records symlink targets without following links, includes hidden files by default, and preserves executable permission bits. Manifest loading and rollback validate paths and blob hashes before mutating the workspace, which protects against malformed snapshots and corrupted blob data.
