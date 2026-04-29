# Sandboxed Agent Execution Platform

This repository is a local sandbox execution platform for coding agents. It lets an agent run commands inside an isolated Docker container, inspect the resulting file changes with `safe-run diff`, and roll those changes back before anything touches the host workspace.

The main project README is at [`../README.md`](../README.md). CI/CD workflow documentation lives under [`workflows/`](workflows/README.md).

## What Works

- Docker sandbox runtime with Python, Node, Git, Bash, and headless Chromium.
- Snapshot, diff, and rollback CLI through `safe-run`.
- FastAPI orchestrator for sandbox create, health, exec streaming, and cleanup.
- Cloudflare Worker control plane for public auth and proxying.
- End-to-end smoke test for Worker -> orchestrator -> Docker -> `safe-run`.
- Demo frontend target that proves the sandbox can make a visible UI change and return a reviewable diff.

## Smallest Remaining Demo Slice

The only meaningful missing layer is a tiny scripted “agent task” wrapper: create a sandbox, run the demo frontend text/color change, return `safe-run diff`, and clean up. A real LLM agent and GitHub PR creation can be follow-ups.
