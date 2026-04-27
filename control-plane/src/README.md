# `control-plane/src/` — Worker source

## What this folder is

TypeScript entrypoint for the Cloudflare Worker (`fetch` handler). Bundled by Wrangler for deploy and local dev. The current router is still a stub backed by an in-memory registry; the next milestone is calling a Docker-backed orchestrator through the configured `SANDBOX_ORCHESTRATOR_URL`.

## Files in this directory

| File | Role |
|------|------|
| [index.ts](index.ts) | Routes: `POST /sandbox/create`, `DELETE /sandbox/:id`, `GET /sandbox/:id/health` |

## Tasks to implement

- [x] Basic routes for sandbox create, destroy, and health
- [ ] Split routers into modules (`sandbox.ts`, `streaming.ts`) as the API grows
- [ ] Shared types for JSON payloads; zod validation on input
- [ ] Middleware: auth, request id, structured logging to Workers Analytics / external sink
