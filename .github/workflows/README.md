# GitHub Actions workflows

## What this folder is

CI pipelines for the Sandboxed Agent Execution Platform: the full Python test suite, Docker image build plus sandbox smoke test, and the local Worker → orchestrator → Docker e2e smoke path.

## Files in this directory

| File | Role |
|------|------|
| [ci.yml](ci.yml) | Installs Python dev/orchestrator dependencies, runs `make test`, builds `sandbox/Dockerfile`, runs `make sandbox-smoke`, and runs the Worker → orchestrator → Docker e2e smoke |

## CI checks

- **Python suite**: installs `.[dev,orchestrator]`, then runs `make test PYTHON=python3` to cover snapshot tests, sandbox contract tests, and control-plane/orchestrator tests.
- **Docker sandbox**: builds `sandbox/Dockerfile` as `saep-sandbox:ci` without pushing, loads it into the runner, then runs `make sandbox-smoke IMAGE_TAG=ci`.
- **Worker/orchestrator e2e**: builds `sandbox/Dockerfile` as `saep-sandbox:ci`, then runs `make e2e-smoke PYTHON=python3 SAEP_SANDBOX_IMAGE=saep-sandbox:ci` to verify Worker → FastAPI orchestrator → Docker sandbox → `safe-run`, including the `demo-frontend/` visual-change diff.
