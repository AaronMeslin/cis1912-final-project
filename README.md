# Sandboxed Agent Execution Platform

This project lets AI coding agents run commands and scripts inside **isolated Docker sandboxes**, with a **snapshot / diff / rollback** layer so workspace changes can be reviewed and undone before they are committed or propagated. A **Cloudflare Workers** control plane (stubbed) will eventually orchestrate sandbox lifecycle, health, and streaming; **Terraform** will wire cloud resources. Everything in this repository is currently **scaffold and stubs**—implement the checklists below before relying on it in production.

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

## Component documentation

| Component | README |
|-----------|--------|
| Docker sandbox image | [sandbox/README.md](sandbox/README.md) |
| Snapshot / diff / rollback CLI | [snapshot/README.md](snapshot/README.md) |
| Control plane API (Workers) | [control-plane/README.md](control-plane/README.md) |
| Infrastructure (Terraform) | [infra/README.md](infra/README.md) |

## Task checklist

### Docker Sandbox

- [ ] Base workspace image with shell, git, Node/Python
- [ ] Headless browser support
- [ ] Security constraints (network allowlist, read-only mounts)
- [ ] Multi-stage Dockerfile

### Snapshot / Diff / Rollback

- [ ] Snapshot working directory before execution
- [ ] Diff engine (created, modified, deleted files, symlinks, hidden files)
- [ ] Rollback system to restore from snapshot
- [ ] CLI: `safe-run <command>`, `safe-run diff`, `safe-run undo`
- [ ] Edge case tests: large binaries, symlinks, hidden files

### Control Plane (Cloudflare Workers)

- [ ] Sandbox lifecycle: create, start, stop, destroy
- [ ] Session streaming
- [ ] Health checks and resource tracking
- [ ] Local testing with Miniflare

### Infrastructure (Terraform)

- [ ] Cloudflare Workers + Docker infra configs
- [ ] Environment parity between local and cloud

### CI/CD

- [ ] Integration tests for sandbox spin-up/teardown
- [ ] Automated diff/rollback tests
- [ ] GitHub Actions workflow

### Observability

- [ ] Session health and lifecycle logging
- [ ] Resource usage metrics (CPU, memory, disk)
- [ ] Execution result tracking

## Local development setup

### Prerequisites

- **Docker** (Engine + CLI) for building and running the sandbox image
- **Python 3.10+** for the snapshot CLI (`snapshot/`)
- **Node.js 18+** and **npm** for Wrangler / Miniflare (control plane)

### Quick commands

```bash
make build          # Build the sandbox Docker image
make test           # Run stub/syntax checks (snapshot Python, etc.)
make dev            # Start the control plane locally (Wrangler dev)
make sandbox-up     # Optional: run sandbox container (see Makefile)
make sandbox-down   # Tear down sandbox container
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

From the repository root (so the `snapshot` package resolves):

```bash
python3 -m snapshot.safe_run --help
# Future: install as `safe-run` on PATH via pip/console_scripts
```

### Terraform

See [infra/README.md](infra/README.md) for `terraform init` / `plan` / `apply`. Do not commit API tokens; use `TF_VAR_*` or a secrets backend in real use.

## License

Specify a license when the project ships (not set in this scaffold).
