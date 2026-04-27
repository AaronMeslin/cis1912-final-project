# `control-plane/orchestrator/` — local Docker orchestrator

This directory contains the local Docker-backed backend that the Cloudflare Worker will proxy to during development and demos. The orchestrator is intentionally separate from `control-plane/src/`, which remains the Worker TypeScript entrypoint.

## Current phase

Phase 1 implements the service skeleton:

- FastAPI app
- `GET /healthz`
- Internal-token auth for sandbox routes
- SQLite registry
- Placeholder sandbox routes returning `501 Not Implemented`

Docker lifecycle, SSE exec streaming, reconciliation, and Worker proxy integration are planned follow-up phases.

## Run locally

From the repository root:

```bash
python3 -m pip install -e ".[orchestrator]"
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
