# `control-plane/orchestrator/` — local Docker orchestrator

This directory contains the local Docker-backed backend that the Cloudflare Worker will proxy to during development and demos. The orchestrator is intentionally separate from `control-plane/src/`, which remains the Worker TypeScript entrypoint.

## Current phase

The current implementation supports local Docker sandbox lifecycle:

- FastAPI app
- `GET /healthz`
- Internal-token auth for sandbox routes
- SQLite registry
- `POST /sandbox/create` to create a real `saep-sandbox:local` container
- `GET /sandbox/:id/health` to inspect container state
- `DELETE /sandbox/:id` to remove the container and registry row
- `POST /sandbox/:id/exec` to stream command output from a sandbox
- Startup reconciliation for stale registry rows and orphaned managed containers

Worker proxy integration is a planned follow-up phase.

## Run locally

From the repository root:

```bash
python3 -m pip install -e ".[orchestrator]"
make build
make orchestrator-up
```

The orchestrator binds to `127.0.0.1:9999` by default. It is local-only; a deployed Cloudflare Worker cannot reach this address.

## Local auth

Sandbox routes require `X-SAEP-Internal-Token` when `SAEP_INTERNAL_TOKEN` is set:

```bash
curl http://127.0.0.1:9999/healthz
curl -X POST http://127.0.0.1:9999/sandbox/create \
  -H "X-SAEP-Internal-Token: dev-internal-token"
```

## Lifecycle routes

```bash
SANDBOX_ID=$(curl -s -X POST http://127.0.0.1:9999/sandbox/create \
  -H "X-SAEP-Internal-Token: dev-internal-token" | python3 -c "import json,sys; print(json.load(sys.stdin)['sandbox_id'])")

curl http://127.0.0.1:9999/sandbox/$SANDBOX_ID/health \
  -H "X-SAEP-Internal-Token: dev-internal-token"

curl -X DELETE http://127.0.0.1:9999/sandbox/$SANDBOX_ID \
  -H "X-SAEP-Internal-Token: dev-internal-token"
```

## Command execution

Commands are sent as JSON arrays and streamed back as server-sent events:

```bash
curl -N -X POST http://127.0.0.1:9999/sandbox/$SANDBOX_ID/exec \
  -H "X-SAEP-Internal-Token: dev-internal-token" \
  -H "Content-Type: application/json" \
  -d '{"command":["safe-run","run","python3","-c","print(\"hi\")"],"timeout":30}'
```

Example response:

```text
event: output
data: {"line": "hi\n", "stream": "stdout"}

event: exit
data: {"code": 0}
```

Only one command can run in a sandbox at a time. Concurrent exec requests for the same sandbox return `409 sandbox_busy` so `safe-run` snapshots cannot overwrite each other.
