# GitHub Actions workflows

## What this folder is

CI pipelines for the Sandboxed Agent Execution Platform: Python snapshot package checks, Docker image build for the sandbox, and Terraform formatting/validation for [`infra/`](../../infra/).

## Files in this directory

| File | Role |
|------|------|
| [ci.yml](ci.yml) | Lint placeholder, `compileall` on `snapshot/`, Docker build of `sandbox/Dockerfile`, `terraform fmt` + `validate` |

## Tasks to implement

- [ ] Add ruff/black/mypy for `snapshot/` when `pyproject.toml` exists
- [ ] Integration test: build image, run container, tear down (needs Docker on runner — already available)
- [ ] Run `pytest` for snapshot diff/rollback when tests exist
- [ ] Add Wrangler dry-run or `wrangler deploy --dry-run` for `control-plane/` when secrets strategy exists
- [ ] Cache pip/npm/terraform providers aggressively
