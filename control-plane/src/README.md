# `control-plane/src/` — Worker source

## What this folder is

TypeScript entrypoint for the Cloudflare Worker (`fetch` handler). Bundled by Wrangler for deploy and local dev.

## Files in this directory

| File | Role |
|------|------|
| [index.ts](index.ts) | Routes: `POST /sandbox/create`, `DELETE /sandbox/:id`, `GET /sandbox/:id/health` |

## Tasks to implement

- [ ] Split routers into modules (`sandbox.ts`, `streaming.ts`) as the API grows
- [ ] Shared types for JSON payloads; zod validation on input
- [ ] Middleware: auth, request id, structured logging to Workers Analytics / external sink
