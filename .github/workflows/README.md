# GitHub Actions workflows

## What this folder is

CI pipelines for the Sandboxed Agent Execution Platform: Python snapshot package checks and tests, Docker image build for the sandbox, and Terraform formatting/validation for [`infra/`](../../infra/).

## Files in this directory

| File | Role |
|------|------|
| [ci.yml](ci.yml) | Installs Python dev dependencies, runs `compileall` and the snapshot `pytest` suite, builds `sandbox/Dockerfile`, runs `terraform fmt` + `validate` |

## Current checks

- **Python snapshot package**: installs `.[dev]`, runs `python3 -m compileall -q snapshot`, then `python3 -m pytest`.
- **Docker sandbox**: builds `sandbox/Dockerfile` as `saep-sandbox:ci` without pushing.
- **Terraform**: runs `terraform fmt -check -recursive infra`, `terraform -chdir=infra init -backend=false -input=false`, and `terraform -chdir=infra validate`.

## Tasks to implement

- [ ] Add ruff/black/mypy for `snapshot/`
- [ ] Integration test: build image, run container, tear down (needs Docker on runner — already available)
- [x] Run `pytest` for snapshot diff/rollback and CLI safety regressions
- [ ] Add Wrangler dry-run or `wrangler deploy --dry-run` for `control-plane/` when secrets strategy exists
- [ ] Cache pip/npm/terraform providers aggressively
