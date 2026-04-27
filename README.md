# Sandboxed Agent Execution Platform

This project lets AI coding agents run commands and scripts inside **isolated Docker sandboxes**, with a **snapshot / diff / rollback** layer so workspace changes can be reviewed and undone before they are committed or propagated. A **Cloudflare Workers** control plane (stubbed) will eventually orchestrate sandbox lifecycle, health, and streaming; **Terraform** will wire cloud resources. The snapshot CLI has a working first vertical slice, and the Docker image now installs that CLI for in-container smoke testing. The control plane and infra are still scaffolds.

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

Flow in words: the **agent** asks the **control plane** to create or use a sandbox; execution and file changes happen in the **sandbox**; the **snapshot engine** records state, diffs changes, and rolls back on demand.

## Current status

The project is in a **local vertical-slice** stage. The snapshot engine is usable and well-tested, and the Docker sandbox now builds a non-root runtime image with `safe-run`, Node, Python, Git, and headless Chromium. CI verifies the snapshot suite, Docker build, Docker smoke path, and Terraform scaffold.

The next major milestone is orchestration: connect the Cloudflare Worker control plane to a local Docker-backed sandbox service so `POST /sandbox/create`, `GET /sandbox/:id/health`, and `DELETE /sandbox/:id` manage real containers instead of returning in-memory placeholders.

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
- [ ] Real Docker-backed sandbox lifecycle: create, start, stop, destroy
- [ ] Session streaming
- [ ] Health checks and resource tracking
- [ ] Local testing with Miniflare

### Infrastructure (Terraform)

- [ ] Cloudflare Workers + Docker infra configs
- [ ] Environment parity between local and cloud

### CI/CD

- [x] Docker sandbox build and `safe-run` smoke test
- [ ] Integration tests for sandbox spin-up/teardown
- [x] Automated diff/rollback tests
- [x] GitHub Actions workflow

### Observability

- [ ] Session health and lifecycle logging
- [ ] Resource usage metrics (CPU, memory, disk)
- [ ] Execution result tracking

## Suggested next steps

1. **Control plane to Docker:** add a minimal local orchestrator that can create, inspect, and remove sandbox containers, then have the Worker call it via `SANDBOX_ORCHESTRATOR_URL`.
2. **Snapshot hardening:** add a run lock for concurrent `safe-run` executions plus large/sparse file coverage.
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
make dev            # Start the control plane locally (Wrangler dev)
make sandbox-up     # Optional: run sandbox container (see Makefile)
make sandbox-down   # Tear down sandbox container
```

For a fresh local Python environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
make test PYTHON=.venv/bin/python
```

### Control plane (Miniflare / Wrangler)

From `control-plane/`:

```bash
cd control-plane
npm install          # once a package.json exists; until then use npx wrangler
npx wrangler dev     # or: npx miniflare src/index.ts (depending on setup)
```

The Worker entrypoint is [control-plane/src/index.ts](control-plane/src/index.ts). See [control-plane/README.md](control-plane/README.md) for routes and env vars.

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

## License

Specify a license when the project ships (not set in this scaffold).
