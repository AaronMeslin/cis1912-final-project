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
- Startup reconciliation for stale registry rows and orphaned managed containers

SSE exec streaming and Worker proxy integration are planned follow-up phases. `POST /sandbox/:id/exec` intentionally still returns `501 Not Implemented`.

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
