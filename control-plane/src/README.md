# `control-plane/src/` — Worker source

## What this folder is

TypeScript entrypoint for the Cloudflare Worker (`fetch` handler). Bundled by Wrangler for deploy and local dev. The router authenticates public callers and proxies sandbox routes to the Docker-backed orchestrator through `SANDBOX_ORCHESTRATOR_URL`.

## Files in this directory

| File | Role |
|------|------|
| [index.ts](index.ts) | Auth + proxy routes: create, health, exec, delete |

## Tasks to implement

- [x] Basic routes for sandbox create, destroy, and health
- [x] Bearer auth for public sandbox routes
- [x] Proxying to the local orchestrator
- [x] SSE passthrough for `/sandbox/:id/exec`
- [ ] Split routers into modules (`sandbox.ts`, `streaming.ts`) as the API grows
- [ ] Shared types for JSON payloads; zod validation on input
- [ ] Middleware: request id, structured logging to Workers Analytics / external sink
