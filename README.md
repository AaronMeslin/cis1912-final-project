# Sandboxed Agent Execution Platform

This project lets AI coding agents run commands inside **isolated Docker sandboxes**. Every run can be snapshotted, diffed, and rolled back before changes are committed or copied back to a real workspace.

The current implementation is a working local vertical slice: a Cloudflare Worker control plane proxies requests to a FastAPI orchestrator, the orchestrator manages Docker sandboxes, and the `safe-run` snapshot engine records file changes. The demo path changes a small static frontend inside the sandbox and returns a reviewable diff.

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

## What works

- Docker sandbox image with Python, Node, Git, Bash, and headless Chromium.
- Snapshot, diff, and rollback through the `safe-run` CLI.
- FastAPI orchestrator for sandbox lifecycle, health checks, command execution, and cleanup.
- Cloudflare Worker API for public auth and proxying to the orchestrator.
- Server-sent event streaming for command output.
- CI coverage for Python tests, Docker smoke tests, Terraform validation, and the local e2e path.
- Demo frontend target that proves a sandbox can make a visible UI change and expose it through `safe-run diff`.

## Component documentation

| Component | README |
|-----------|--------|
| Docker sandbox image | [sandbox/README.md](sandbox/README.md) |
| Snapshot / diff / rollback CLI | [snapshot/README.md](snapshot/README.md) |
| Control plane API (Workers) | [control-plane/README.md](control-plane/README.md) |
| Demo frontend target | [demo-frontend/README.md](demo-frontend/README.md) |
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
- [x] CI job for full Worker → orchestrator → Docker e2e smoke

### Observability

- [ ] Session health and lifecycle logging
- [ ] Resource usage metrics (CPU, memory, disk)
- [ ] Execution result tracking

## What is left

The core platform is working locally. The smallest useful next step is a scripted agent task layer: one command or endpoint that creates a sandbox, runs the demo frontend change, returns `safe-run diff`, and cleans up. Full LLM planning, GitHub PR creation, cloud deployment, and deeper sandbox hardening are natural follow-ups.

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
make orchestrator-test   # Run FastAPI orchestrator and Worker contract tests
make orchestrator-up     # Start the Worker-compatible FastAPI orchestrator
make e2e-smoke           # Run Worker → orchestrator → Docker → safe-run demo smoke test
make e2e-smoke SAEP_SANDBOX_IMAGE=saep-sandbox:ci  # Use a specific sandbox image
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

This verifies the public local Worker API all the way through Docker and `safe-run`, including a small PR-demo style frontend change:

```bash
.venv/bin/python -m pip install -e ".[dev,orchestrator]"
make build
make e2e-smoke PYTHON=.venv/bin/python
```

The `make e2e-smoke` target runs pytest with live logs enabled (`-s`), so you should see `[e2e] ...` progress messages in your terminal. The smoke test:

1. Checks Docker is running and `saep-sandbox:local` exists
2. Starts the local FastAPI orchestrator on `127.0.0.1:9999`
3. Starts Wrangler on `127.0.0.1:8787`
4. Calls the Worker API to create a sandbox
5. Runs `safe-run run` inside the sandbox to create `f.txt`
6. Runs `safe-run diff` and verifies `created f.txt`
7. Seeds the sandbox with this repo, changes `demo-frontend/index.html` and `demo-frontend/styles.css`, and verifies `safe-run diff` reports both files as modified
8. Deletes the sandbox and stops both local processes

Expected final output:

```text
[e2e] SAEP e2e smoke test completed successfully
1 passed
```

If the sandbox image is missing, the e2e test skips with `run make build first`.

### Demo frontend

The `demo-frontend/` folder is a static visual target for the PR-demo path. Open `demo-frontend/index.html` in a browser to see the baseline page. The e2e smoke test asks the sandbox to change the headline from `Sandbox Demo` to `Sandbox Agent Demo` and the accent color from blue to purple, then checks that `safe-run diff` reports those files as modified.

### CI coverage

GitHub Actions runs the same paths used locally:

- `python-tests` installs `.[dev,orchestrator]` and runs `make test PYTHON=python3`, covering snapshot tests, sandbox contract tests, and control-plane/orchestrator tests.
- `docker-sandbox` builds `sandbox/Dockerfile` as `saep-sandbox:ci` and runs `make sandbox-smoke IMAGE_TAG=ci`.
- `worker-orchestrator-e2e` builds `saep-sandbox:ci` and runs `make e2e-smoke PYTHON=python3 SAEP_SANDBOX_IMAGE=saep-sandbox:ci`.
- `terraform` runs formatting, backend-free init, and validation for `infra/`.

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

`make orchestrator-up` starts the single supported local orchestrator: the FastAPI backend used by the Worker and e2e smoke path. It exposes sandbox create, health, exec streaming, and delete routes under `/sandbox/...`.

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

