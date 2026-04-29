# `control-plane/src/` — Worker source

## What this folder is

TypeScript entrypoint for the Cloudflare Worker (`fetch` handler). Bundled by Wrangler for deploy and local dev. The router authenticates public callers and proxies sandbox routes to the Docker-backed orchestrator through `SANDBOX_ORCHESTRATOR_URL`.

## Files in this directory

| File | Role |
|------|------|
| [index.ts](index.ts) | Auth + proxy routes: create, health, exec, delete |

The Worker exposes the sandbox create, health, exec, and delete routes used by the local demo and e2e smoke test.
