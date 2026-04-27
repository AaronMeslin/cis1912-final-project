# `control-plane/` — Cloudflare Workers API

## What this component is

This Worker is the **HTTP control plane** between AI agents (or a broker) and **sandbox instances**. It exposes lifecycle and health endpoints. Today it is a **stub**: routes return JSON placeholders and keep an in-memory registry only (lost on cold start).

Production shape will call a **sandbox orchestrator** (Docker socket API, remote agent, Kubernetes, etc.) using URLs and secrets from Terraform / Wrangler.

The Docker sandbox runtime now exists and is smoke-tested in CI, so the next control-plane milestone is to replace the placeholder registry behavior with calls to a local Docker-backed orchestrator.

## Files in this directory

| File | Role |
|------|------|
| [wrangler.toml](wrangler.toml) | Worker name, entrypoint, compatibility date, stub `vars` |
| [src/index.ts](src/index.ts) | `fetch` router: create, delete, health |

## HTTP API (stubbed)

| Method | Path | Behavior (target) |
|--------|------|-------------------|
| `POST` | `/sandbox/create` | Provision a new sandbox; return `sandboxId` |
| `DELETE` | `/sandbox/:id` | Stop and destroy sandbox `id` |
| `GET` | `/sandbox/:id/health` | Health + resource snapshot |

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
curl -s -X POST http://127.0.0.1:8787/sandbox/create
curl -s http://127.0.0.1:8787/sandbox/<id>/health
curl -s -X DELETE http://127.0.0.1:8787/sandbox/<id>
```

Environment variables from `[vars]` in `wrangler.toml` appear on `env` in the Worker. Use `wrangler secret put ...` for tokens (not committed).

## Tasks to implement

- [x] Stub routes for create, destroy, and health
- [ ] Replace in-memory `sandboxRegistry` with D1, KV, or external service
- [ ] Implement real create/destroy against Docker/orchestrator (`SANDBOX_ORCHESTRATOR_URL`)
- [ ] Add authentication (Bearer token, CF Access, or signed requests)
- [ ] Session streaming (WebSocket or SSE) for attach/logs
- [ ] Health: aggregate CPU, memory, disk from orchestrator
- [ ] Rate limits and per-tenant quotas (Cloudflare rate limiting + metadata)
- [ ] Integration tests hitting Miniflare or `wrangler dev` in CI
