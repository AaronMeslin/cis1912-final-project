# Sandboxed Agent Execution Platform

This project lets AI coding agents run commands and scripts inside **isolated Docker sandboxes**, with a **snapshot / diff / rollback** layer so workspace changes can be reviewed and undone before they are committed or propagated. A local **Cloudflare Workers** control plane now authenticates and proxies sandbox lifecycle, health, and command-exec requests to a Docker-backed orchestrator; **Terraform** will wire cloud resources later. The snapshot CLI, Docker image, local orchestrator, Worker proxy, and end-to-end smoke path are working locally.

## Architecture

```
                    +-------------------+
                    |  AI coding agent  |
                    |  (Cursor, CLI…)   |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |   Control plane   |
                    | Cloudflare Worker |
                    | (create/destroy,  |
                    |  health, future   |
                    |  streaming)       |
                    +---------+---------+
                              |
              +---------------+---------------+
              |                               |
              v                               v
    +-------------------+           +-------------------+
    | Docker sandbox    |           | Snapshot engine |
    | (workspace image: |<--------->| safe-run, diff, |
    |  shell, git,      |  FS ops   | undo (Python)   |
    |  Node, Python,    |           +-------------------+
    |  headless Chrome) |
    +-------------------+
```

Flow in words: the **agent** asks the **control plane** to create or use a sandbox; the Worker proxies to the local orchestrator; execution and file changes happen in the **sandbox**; the **snapshot engine** records state, diffs changes, and rolls back on demand.

## Current status

The project is in a **local vertical-slice** stage. The snapshot engine is usable and well-tested, and the Docker sandbox builds a non-root runtime image with `safe-run`, Node, Python, Git, and headless Chromium. The local control plane now supports the full path: Wrangler Worker → FastAPI orchestrator → Docker sandbox → `safe-run`.

The next major milestone is packaging the demo and CI flow around the local end-to-end smoke test, then adding the GitHub PR demo task.

## Component documentation

| Component | README |
|-----------|--------|
| Docker sandbox image | [sandbox/README.md](sandbox/README.md) |
| Snapshot / diff / rollback CLI | [snapshot/README.md](snapshot/README.md) |
| Control plane API (Workers) | [control-plane/README.md](control-plane/README.md) |
| Infrastructure (Terraform) | [infra/README.md](infra/README.md) |

## Task checklist

### Docker Sandbox

- [x] Base workspace image with shell, git, Node/Python
- [x] Headless browser support
- [x] Non-root runtime user with writable `/workspace`
- [x] `safe-run` installed inside the sandbox image
- [x] Sandbox healthcheck and Docker smoke test
- [ ] Security constraints (network allowlist, read-only mounts)
- [x] Multi-stage Dockerfile

### Snapshot / Diff / Rollback

- [x] Snapshot working directory before execution
- [x] Diff engine (created, modified, deleted files, symlinks, hidden files)
- [x] Rollback system to restore from snapshot
- [x] CLI: `safe-run <command>`, `safe-run diff`, `safe-run undo`
- [x] Safety tests for tampered manifests, `.saep` tampering, corrupt blobs, symlinks, hidden files, modes, and read-only directories
- [ ] Edge case tests: large binaries, sparse files, and concurrent runs

### Control Plane (Cloudflare Workers)

- [x] Stub lifecycle routes: create, health, destroy
- [x] Real Docker-backed sandbox lifecycle: create, start, stop, destroy
- [x] SSE command-output streaming via `/sandbox/:id/exec`
- [x] Health checks through the local Docker orchestrator
- [x] Local testing with Wrangler / local Workers runtime
- [ ] Resource usage tracking

### Infrastructure (Terraform)

- [ ] Cloudflare Workers + Docker infra configs
- [ ] Environment parity between local and cloud

### CI/CD

- [x] Docker sandbox build and `safe-run` smoke test
- [x] Integration tests for sandbox spin-up/teardown
- [x] Automated diff/rollback tests
- [x] GitHub Actions workflow
- [ ] CI job for full Worker → orchestrator → Docker e2e smoke

### Observability

- [ ] Session health and lifecycle logging
- [ ] Resource usage metrics (CPU, memory, disk)
- [ ] Execution result tracking

## Suggested next steps

1. **End-to-end demo:** use the local Worker API to create a sandbox, execute a coding task, inspect `safe-run diff`, and clean up.
2. **CI e2e hardening:** run the full Worker → orchestrator → Docker smoke test in GitHub Actions after building the sandbox image.
3. **Sandbox hardening:** document and test runtime flags for network policy, read-only root filesystem, tmpfs, dropped capabilities, and resource limits.

## Local development setup

### Prerequisites

- **Docker** (Engine + CLI) for building and running the sandbox image
- **Python 3.10+** for the snapshot CLI (`snapshot/`)
- **Node.js 18+** and **npm** for Wrangler / Miniflare (control plane)

### Quick commands

```bash
make build          # Build the sandbox Docker image
make test           # Run snapshot Python compile check + pytest suite
make sandbox-smoke  # Run safe-run diff/undo inside the Docker sandbox
make orchestrator-dev    # Start the simple top-level lifecycle orchestrator
make orchestrator-test   # Run orchestrator and Worker contract tests
make orchestrator-smoke  # Create, health-check, and destroy through the simple orchestrator
make orchestrator-up     # Start the Worker-compatible FastAPI orchestrator
make e2e-smoke           # Run Worker → orchestrator → Docker → safe-run smoke test
make dev                 # Start the control plane locally (Wrangler dev)
make sandbox-up     # Optional: run sandbox container (see Makefile)
make sandbox-down   # Tear down sandbox container
```

For a fresh local Python environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,orchestrator]"
make test PYTHON=.venv/bin/python
```

### Full local end-to-end smoke test

This verifies the public local Worker API all the way through Docker and `safe-run`:

```bash
.venv/bin/python -m pip install -e ".[dev,orchestrator]"
make build
make e2e-smoke PYTHON=.venv/bin/python
```

The smoke test starts the local FastAPI orchestrator on `127.0.0.1:9999`, starts Wrangler on `127.0.0.1:8787`, calls the Worker API to create a sandbox, runs `safe-run run` to create `f.txt`, runs `safe-run diff`, verifies `created f.txt`, and destroys the sandbox.

If the sandbox image is missing, the e2e test skips with `run make build first`.

### Manual control plane testing (Wrangler + local orchestrator)

In terminal 1:

```bash
make orchestrator-up
```

In terminal 2:

```bash
cd control-plane
npx wrangler dev
```

The Worker entrypoint is [control-plane/src/index.ts](control-plane/src/index.ts). See [control-plane/README.md](control-plane/README.md) for routes and env vars.

### Docker-backed sandbox lifecycle

There are currently two local orchestrator entrypoints:

- `make orchestrator-dev` starts the top-level lifecycle orchestrator (`POST /sandboxes`, `GET /sandboxes/:id/health`, `DELETE /sandboxes/:id`).
- `make orchestrator-up` starts the Worker-compatible FastAPI orchestrator (`POST /sandbox/create`, `POST /sandbox/:id/exec`, health, and delete) used by the e2e smoke path.

For the simple lifecycle smoke test:

```bash
make build
make orchestrator-dev
make orchestrator-smoke
```

Example public Worker API calls:

```bash
curl -s -X POST http://127.0.0.1:8787/sandbox/create \
  -H "Authorization: Bearer dev-api-key"

curl -N -X POST http://127.0.0.1:8787/sandbox/<id>/exec \
  -H "Authorization: Bearer dev-api-key" \
  -H "Content-Type: application/json" \
  -d '{"command":["safe-run","diff"],"timeout":30}'

curl -s -X DELETE http://127.0.0.1:8787/sandbox/<id> \
  -H "Authorization: Bearer dev-api-key"
```


### Snapshot CLI

From the repository root, either run the module directly or install the editable package:

```bash
python3 -m snapshot.safe_run --help
safe-run --help        # after `pip install -e ".[dev]"`
```

Manual smoke test in a throwaway workspace:

```bash
mkdir -p /tmp/saep-manual-test
cd /tmp/saep-manual-test
safe-run run python3 -c "open('hello.txt', 'w').write('hi')"
safe-run diff
safe-run undo
```

Expected output includes `created hello.txt` from `diff` and `removed hello.txt` from `undo`.

### Terraform

See [infra/README.md](infra/README.md) for `terraform init` / `plan` / `apply`. Do not commit API tokens; use `TF_VAR_*` or a secrets backend in real use.

