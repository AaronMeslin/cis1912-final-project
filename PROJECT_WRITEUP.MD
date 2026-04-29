# Sandboxed Agent Execution Platform — Project Writeup

## 1. Project description and accomplishments

This project is a local-first platform for running AI coding-agent tasks inside isolated Docker sandboxes. The motivation is that useful coding agents need to run real commands: cloning or editing code, installing dependencies, running tests, and inspecting output. Running that directly on a developer's machine is risky, so this project places a control layer around agent execution.

At a high level, the system works like this:

```text
Developer / agent
    → Cloudflare Worker public API
    → FastAPI orchestrator
    → Docker sandbox runtime
    → /workspace mounted directory
    → safe-run snapshot / diff / rollback
```

The current implementation accomplishes a complete local vertical slice:

- A **Cloudflare Worker** exposes a public HTTP API for sandbox operations.
- A **FastAPI orchestrator** receives trusted internal requests from the Worker and controls Docker.
- The orchestrator creates a host workspace folder, starts a Docker container, and bind-mounts that folder into the container at `/workspace`.
- Commands run inside the sandbox through `POST /sandbox/:id/exec`.
- The sandbox image includes the `safe-run` CLI, which snapshots the workspace before a command, then allows changes to be diffed or rolled back.
- The platform can stream command output back to the caller using Server-Sent Events.
- The demo flow seeds the sandbox with this repo, modifies files in `demo-frontend/`, runs `safe-run diff`, returns the diff, and cleans up the sandbox.

The result is a working local demo of the core idea: an agent can make code changes inside a reproducible sandbox, and the developer can inspect exactly what changed before accepting those changes.

## 2. Relevant code explanation

### Cloudflare Worker public API

Relevant files:

- `control-plane/src/index.ts`
- `control-plane/wrangler.toml`

The Worker is the public API boundary. It exposes routes such as:

```text
POST   /sandbox/create
GET    /sandbox/:id/health
POST   /sandbox/:id/exec
DELETE /sandbox/:id
```

The Worker checks public Bearer-token authentication, then proxies valid sandbox requests to the local orchestrator. It also forwards an internal token using the `x-saep-internal-token` header. The Worker does not directly create containers, touch the filesystem, or run commands. Its job is to act as the public API gateway: authenticate, route, and proxy.

### FastAPI Docker orchestrator

Relevant files:

- `control-plane/orchestrator/main.py`
- `control-plane/orchestrator/docker_client.py`
- `control-plane/orchestrator/registry.py`
- `control-plane/orchestrator/models.py`
- `control-plane/orchestrator/locks.py`

The orchestrator is the privileged backend that actually controls Docker. It is implemented with FastAPI and the Docker SDK for Python.

The main responsibilities are:

- create a sandbox record in SQLite
- create a workspace directory on the host
- optionally seed that workspace with files from this repository
- start a Docker container using the configured sandbox image
- mount the host workspace into the container as `/workspace`
- execute commands inside the container
- stream command output as SSE
- delete containers and registry rows during cleanup
- reconcile stale registry/container state on startup

The Docker bind mount is the key filesystem mechanism:

```text
host workspace directory
    ↔ mounted into container as /workspace
```

This means that files modified inside Docker under `/workspace` are the same files in the host workspace directory. In the current API, an external agent modifies those files by sending exec commands to the orchestrator rather than by directly editing host files.

### Docker sandbox runtime

Relevant files:

- `sandbox/Dockerfile`
- `sandbox/healthcheck.sh`

The sandbox image provides the environment where agent commands run. It includes:

- Bash and standard shell tools
- Git
- Python
- Node.js
- headless Chromium
- the project `safe-run` CLI

The container runs as a non-root `agent` user and uses `/workspace` as the working directory. The Docker smoke test mounts a temporary workspace and verifies that `safe-run run`, `safe-run diff`, and `safe-run undo` work inside the container.

### Snapshot engine and `safe-run`

Relevant files:

- `snapshot/safe_run.py`
- `snapshot/snapshot.py`
- `snapshot/diff.py`
- `snapshot/rollback.py`

The snapshot engine is the safety layer around command execution. The main CLI is `safe-run`.

Typical usage:

```bash
SAFE_RUN="$(pwd)/.venv/bin/safe-run"
WORKSPACE="$(mktemp -d /tmp/saep-safe-run-demo-XXXXXX)"
cd "$WORKSPACE"
"$SAFE_RUN" run python3 -c "open('hello.txt', 'w').write('hi')"
"$SAFE_RUN" diff
"$SAFE_RUN" undo
```

`safe-run run` snapshots the workspace before running a command. `safe-run diff` compares the current workspace to the previous snapshot. `safe-run undo` restores the workspace to the previous snapshot.

The snapshot system handles created, modified, and deleted files; directories; dotfiles; symlinks; executable permissions; and corrupted/tampered snapshot metadata. It ignores `.git/` and `.saep/` so that Git metadata and the snapshot store are not themselves captured.

In the sandboxed-agent flow, `safe-run` runs inside Docker against `/workspace`.

### Demo frontend

Relevant files:

- `demo-frontend/index.html`
- `demo-frontend/styles.css`
- `demo-frontend/README.md`

The demo frontend is a small static page used as a visible target for a sandboxed code change. The demo task changes:

- headline text from `Sandbox Demo` to `Sandbox Agent Demo`
- accent color from `#2563eb` to `#7c3aed`

Then it runs `safe-run diff` and verifies that both frontend files are reported as modified.

### Demo task runner

Relevant files:

- `scripts/run_demo_task.py`
- `tests/scripts/test_run_demo_task.py`

The demo task runner wraps the full local demo into one command:

```bash
make demo-task
```

It starts a temporary local orchestrator and Wrangler Worker, creates a sandbox through the Worker API, runs the existing demo edit command in the sandbox, runs `safe-run diff`, prints the diff output, and cleans up the sandbox.

## 3. How to test or view what was built

### Prerequisites

Install the required local tools:

- Docker
- Python 3.10+
- Node.js 18+ and npm

Set up the Python environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,orchestrator]"
```

Build the sandbox image:

```bash
make build
```

### Run the automated tests

Run the main Python test suite:

```bash
make test PYTHON=.venv/bin/python
```

This covers:

- snapshot/diff/rollback behavior
- sandbox image contracts
- FastAPI orchestrator routes
- Worker proxy contract checks
- demo task script behavior

Run the Docker sandbox smoke test:

```bash
make sandbox-smoke
```

This verifies `safe-run run`, `safe-run diff`, and `safe-run undo` inside the Docker sandbox image.

Run the full local end-to-end smoke test:

```bash
make e2e-smoke PYTHON=.venv/bin/python
```

This starts the local orchestrator and Worker, creates a Docker sandbox, runs commands inside it, checks `safe-run diff`, modifies the demo frontend, verifies the diff, and tears everything down.

### Run the presentation demo

The shortest way to view the main demo is:

```bash
make demo-task PYTHON=.venv/bin/python
```

Expected output:

```text
modified demo-frontend/index.html (content changed)
modified demo-frontend/styles.css (content changed)
```

This command proves the main project flow:

1. start local orchestrator
2. start local Worker
3. create a sandbox through the Worker API
4. seed the sandbox workspace with the repo
5. run the frontend edit command inside Docker
6. run `safe-run diff`
7. print the diff
8. delete the sandbox

### Manually run the Worker and orchestrator

In one terminal:

```bash
make orchestrator-up PYTHON=.venv/bin/python
```

In another terminal:

```bash
make dev
```

Then call the Worker API:

```bash
SANDBOX_ID=$(curl -s -X POST http://127.0.0.1:8787/sandbox/create \
  -H "Authorization: Bearer dev-api-key" \
  | python3 -c "import json, sys; print(json.load(sys.stdin)['sandbox_id'])")
```

Run a command in the sandbox through `safe-run`:

```bash
curl -N -X POST http://127.0.0.1:8787/sandbox/$SANDBOX_ID/exec \
  -H "Authorization: Bearer dev-api-key" \
  -H "Content-Type: application/json" \
  -d '{"command":["safe-run","run","python3","-c","open(\"manual.txt\", \"w\").write(\"hello\")"],"timeout":30}'
```

Inspect the diff:

```bash
curl -N -X POST http://127.0.0.1:8787/sandbox/$SANDBOX_ID/exec \
  -H "Authorization: Bearer dev-api-key" \
  -H "Content-Type: application/json" \
  -d '{"command":["safe-run","diff"],"timeout":30}'
```

And clean up:

```bash
curl -s -X DELETE http://127.0.0.1:8787/sandbox/$SANDBOX_ID \
  -H "Authorization: Bearer dev-api-key"
```

### View the demo frontend directly

Open:

```text
demo-frontend/index.html
```

in a browser to see the baseline static page. The sandbox demo modifies this page inside Docker, but does not change the repo copy on the host because the demo runs in a temporary seeded workspace.
