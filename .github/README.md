# Sandboxed Agent Execution Platform

This repository is a local sandbox execution platform for coding agents. It lets an agent run commands inside an isolated Docker container, inspect the resulting file changes with `safe-run diff`, and roll those changes back before anything touches the host workspace.

The architecture is: Cloudflare Worker API -> FastAPI orchestrator -> Docker sandbox runtime -> `safe-run` snapshot engine. The demo path changes a small static frontend inside the sandbox and returns a reviewable diff.

The main project README is at [`../README.md`](../README.md). CI/CD workflow documentation lives under [`workflows/`](workflows/README.md).
