# `sandbox/` — Docker workspace image

## What this component is

This directory defines the **OCI image** that agents use as an isolated workspace: shell, Git, Node.js, Python, the project `safe-run` CLI, and **headless Chromium** for browser automation. The Dockerfile is multi-stage and the runtime defaults to a non-root `agent` user.

Container lifecycle, volume mounts, and execution policy are handled by the local orchestrator in [`../control-plane/orchestrator/`](../control-plane/orchestrator/).

## Files in this directory

| File | Role |
|------|------|
| [Dockerfile](Dockerfile) | Multi-stage build: base packages, Node, Python, Chromium, `safe-run`, non-root runtime user, healthcheck |
| [healthcheck.sh](healthcheck.sh) | Verifies required tools and writable `/workspace` inside the runtime image |
| [../.dockerignore](../.dockerignore) | Keeps the repo-root Docker build context small while still including `pyproject.toml`, `snapshot/`, and sandbox files |

## Build and run (local)

From the repository root:

```bash
make build
# or
docker build -t saep-sandbox:local -f sandbox/Dockerfile .
```

The runtime image defaults to a non-root `agent` user with `/workspace` as its working directory. Run an interactive shell (development only):

```bash
docker run --rm -it saep-sandbox:local bash
```

Run the Docker smoke test from the repo root:

```bash
make sandbox-smoke
```

The smoke test mounts a throwaway workspace and runs `safe-run run`, `safe-run diff`, and `safe-run undo` inside the container.

`make sandbox-up` / `make sandbox-down` in the root [Makefile](../Makefile) start/stop a long-running container name for `docker exec` workflows. The image also includes Docker `HEALTHCHECK`, which runs `/usr/local/bin/saep-healthcheck`.

## Runtime notes

- The image runs as `agent` with `/workspace` as the working directory.
- `safe-run` is installed in the image so commands can be snapshotted, diffed, and rolled back inside mounted workspaces.
- `/usr/local/bin/saep-healthcheck` verifies the tools needed by the local sandbox runtime.
