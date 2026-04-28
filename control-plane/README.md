# `control-plane/` — Cloudflare Workers API

## What this component is

This Worker is the **HTTP control plane** between AI agents (or a broker) and **sandbox instances**. It authenticates public API requests and proxies lifecycle, health, and exec calls to the local Docker-backed orchestrator in [`orchestrator/`](orchestrator/).

Production shape will call a reachable **sandbox orchestrator** (Docker socket API, remote agent, Kubernetes, etc.) using URLs and secrets from Terraform / Wrangler.

For local development, Wrangler serves the Worker on `127.0.0.1:8787` and proxies to the orchestrator on `127.0.0.1:9999`. A deployed Worker cannot reach a developer machine's localhost; production hosting remains future infrastructure work.

## Files in this directory

| File | Role |
|------|------|
| [wrangler.toml](wrangler.toml) | Worker name, entrypoint, compatibility date, local demo `vars` |
| [src/index.ts](src/index.ts) | `fetch` router: auth + proxy to orchestrator |
| [orchestrator/](orchestrator/) | Local FastAPI + Docker backend |

## HTTP API

All sandbox routes require:

```text
Authorization: Bearer dev-api-key
```

| Method | Path | Behavior |
|--------|------|----------|
| `POST` | `/sandbox/create` | Proxy sandbox creation to orchestrator |
| `GET` | `/sandbox/:id/health` | Proxy sandbox health inspection |
| `POST` | `/sandbox/:id/exec` | Proxy command execution and preserve SSE output |
| `DELETE` | `/sandbox/:id` | Proxy sandbox teardown |

The repository also includes a top-level lifecycle-only local orchestrator for simple Docker demos. That server exposes `POST /sandboxes`, `GET /sandboxes/:id/health`, and `DELETE /sandboxes/:id`; the Worker-compatible FastAPI orchestrator in this directory exposes the `/sandbox/...` routes above.

## Local development (Wrangler / Miniflare)

Start the Docker orchestrator first:

```bash
make orchestrator-up
```

Then start Wrangler in another terminal:

```bash
cd control-plane
npx wrangler dev
```

Example:

```bash
curl -s -X POST http://127.0.0.1:8787/sandbox/create \
  -H "Authorization: Bearer dev-api-key"

curl -s http://127.0.0.1:8787/sandbox/<id>/health \
  -H "Authorization: Bearer dev-api-key"

curl -N -X POST http://127.0.0.1:8787/sandbox/<id>/exec \
  -H "Authorization: Bearer dev-api-key" \
  -H "Content-Type: application/json" \
  -d '{"command":["echo","hello"],"timeout":30}'

curl -s -X DELETE http://127.0.0.1:8787/sandbox/<id> \
  -H "Authorization: Bearer dev-api-key"
```

Environment variables from `[vars]` in `wrangler.toml` appear on `env` in the Worker. Use `wrangler secret put ...` for tokens (not committed).

## Tasks to implement

- [x] Stub routes for create, destroy, and health
- [x] Replace in-memory `sandboxRegistry` with orchestrator proxying
- [x] Implement real create/destroy against Docker/orchestrator (`SANDBOX_ORCHESTRATOR_URL`)
- [x] Add authentication (Bearer token locally; secrets in real deployments)
- [x] Session streaming via SSE passthrough for command output
- [x] Health: proxy Docker status + CPU/memory placeholders from orchestrator
- [ ] Rate limits and per-tenant quotas (Cloudflare rate limiting + metadata)
- [ ] Integration tests hitting Miniflare or `wrangler dev` in CI
