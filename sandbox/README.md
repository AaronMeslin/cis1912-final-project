# `sandbox/` — Docker workspace image

## What this component is

This directory defines the **OCI image** that agents use as an isolated workspace: shell, Git, Node.js, Python, and **headless Chromium** for browser automation. The Dockerfile is intentionally **multi-stage** so we can later split “tooling build” from “minimal runtime” and add hardening without rewriting the whole file.

Orchestration (who starts the container, with which volumes and network policy) lives outside this folder—eventually the **control plane** and/or Terraform will document the exact `docker run` / Kubernetes equivalents.

## Files in this directory

| File | Role |
|------|------|
| [Dockerfile](Dockerfile) | Multi-stage build: base packages, Node, Python, Chromium; `CMD` stub |
| [.dockerignore](.dockerignore) | Keeps build context small; excludes dev artifacts |

## Build and run (local)

From the repository root:

```bash
make build
# or
docker build -t saep-sandbox:local -f sandbox/Dockerfile sandbox
```

Run an interactive shell (development only):

```bash
docker run --rm -it saep-sandbox:local bash
```

`make sandbox-up` / `make sandbox-down` in the root [Makefile](../Makefile) start/stop a long-running container name for `docker exec` workflows.

## Security constraints (target state)

- **Network allowlist**: only approved egress (package registries, Git hosts, internal APIs). Implement with Docker networks, firewall sidecars, or a transparent proxy—**not** done in the Dockerfile alone.
- **Read-only root filesystem**: run with `--read-only` and tmpfs for writable paths; mount workspace as a volume with explicit permissions.
- **Non-root user**: add a `USER` in Dockerfile and match host UID/GID if mounting volumes.
- **Capability dropping**: `--cap-drop=all` and add only what Chromium needs (often none beyond default if using userns).

## Tasks to implement

- [ ] Pin base image digest and Node/Python versions for reproducible builds
- [ ] Add dedicated non-root `USER` and fix file permissions under `/workspace`
- [ ] Document minimal Chromium dependency set (or switch to Playwright base image)
- [ ] Wire `CHROME_BIN` / flags for headless-only, no sandbox escalation issues in container
- [ ] Add healthcheck script used by control plane `GET /sandbox/:id/health`
- [ ] Integrate network policy documentation with [control-plane/README.md](../control-plane/README.md) and [infra/README.md](../infra/README.md)
