# `control-plane/` — Cloudflare Workers API

## What this component is

This Worker is the **HTTP control plane** between AI agents (or a broker) and **sandbox instances**. It exposes lifecycle and health endpoints and proxies them to the local Docker-backed orchestrator configured by `SANDBOX_ORCHESTRATOR_URL`.

Production shape will use the same boundary with a remote sandbox orchestrator or managed compute backend.

The local orchestrator API is:

| Method | Path | Behavior |
|--------|------|----------|
| `POST` | `/sandboxes` | Create and start a Docker sandbox |
| `GET` | `/sandboxes/:id/health` | Inspect sandbox status and Docker health |
| `DELETE` | `/sandboxes/:id` | Remove the sandbox container |

## Files in this directory

| File | Role |
|------|------|
| [wrangler.toml](wrangler.toml) | Worker name, entrypoint, compatibility date, stub `vars` |
| [src/index.ts](src/index.ts) | `fetch` router: create, delete, health through orchestrator |

## HTTP API

| Method | Path | Behavior |
|--------|------|-------------------|
| `POST` | `/sandbox/create` | Proxy to `POST /sandboxes`; return `sandboxId` |
| `DELETE` | `/sandbox/:id` | Proxy to `DELETE /sandboxes/:id` |
| `GET` | `/sandbox/:id/health` | Proxy to `GET /sandboxes/:id/health` |

TODO: `POST /sandbox/:id/exec` or WebSocket for **session streaming**; `POST` start/stop if lifecycle is split.

## Local development (Wrangler / Miniflare)

Install dev dependencies once Wrangler is added to a `package.json`, or use `npx`:

```bash
cd control-plane
npx wrangler dev
```

Wrangler bundles with **Miniflare** for local simulation. Open the URL Wrangler prints (often `http://127.0.0.1:8787`).

Example:

```bash
make orchestrator-dev

curl -s -X POST http://127.0.0.1:8787/sandbox/create
curl -s http://127.0.0.1:8787/sandbox/<id>/health
curl -s -X DELETE http://127.0.0.1:8787/sandbox/<id>
```

Environment variables from `[vars]` in `wrangler.toml` appear on `env` in the Worker. Use `wrangler secret put ...` for tokens (not committed).

## Tasks to implement

- [x] Stub routes for create, destroy, and health
- [x] Replace in-memory `sandboxRegistry` with orchestrator calls
- [x] Implement create/health/destroy against Docker/orchestrator (`SANDBOX_ORCHESTRATOR_URL`)
- [ ] Add authentication (Bearer token, CF Access, or signed requests)
- [ ] Session streaming (WebSocket or SSE) for attach/logs
- [x] Health: container status and Docker health from orchestrator
- [ ] Resource usage: CPU, memory, disk from orchestrator
- [ ] Rate limits and per-tenant quotas (Cloudflare rate limiting + metadata)
- [ ] Integration tests hitting Miniflare or `wrangler dev` in CI
