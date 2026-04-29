# GitHub Actions workflows

## What this folder is

CI pipelines for the Sandboxed Agent Execution Platform: the full Python test suite, Docker image build plus sandbox smoke test, the local Worker → orchestrator → Docker e2e smoke path, and Terraform formatting/validation for [`infra/`](../../infra/).

## Files in this directory

| File | Role |
|------|------|
| [ci.yml](ci.yml) | Installs Python dev/orchestrator dependencies, runs `make test`, builds `sandbox/Dockerfile`, runs `make sandbox-smoke`, runs the Worker → orchestrator → Docker e2e smoke, runs `terraform fmt` + `validate` |

## Current checks

- **Python suite**: installs `.[dev,orchestrator]`, then runs `make test PYTHON=python3` to cover snapshot tests, sandbox contract tests, and control-plane/orchestrator tests.
- **Docker sandbox**: builds `sandbox/Dockerfile` as `saep-sandbox:ci` without pushing, loads it into the runner, then runs `make sandbox-smoke IMAGE_TAG=ci`.
- **Worker/orchestrator e2e**: builds `sandbox/Dockerfile` as `saep-sandbox:ci`, then runs `make e2e-smoke PYTHON=python3 SAEP_SANDBOX_IMAGE=saep-sandbox:ci` to verify Worker → FastAPI orchestrator → Docker sandbox → `safe-run`, including the `demo-frontend/` visual-change diff.
- **Terraform**: runs `terraform fmt -check -recursive infra`, `terraform -chdir=infra init -backend=false -input=false`, and `terraform -chdir=infra validate`.

## Tasks to implement

- [ ] Add ruff/black/mypy for `snapshot/` and `control-plane/orchestrator/`
- [x] Integration smoke test: build image, run container, verify `safe-run run/diff/undo`, tear down
- [x] Run `pytest` for snapshot diff/rollback and CLI safety regressions
- [x] Run local Worker → orchestrator → Docker e2e smoke in CI
- [ ] Add Wrangler dry-run or `wrangler deploy --dry-run` for `control-plane/` when secrets strategy exists
- [ ] Cache pip/npm/terraform providers aggressively
