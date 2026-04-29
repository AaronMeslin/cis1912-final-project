# `infra/` — Terraform (Cloudflare + future providers)

## What this component is

This directory holds the Terraform scaffold for the platform. The current [`main.tf`](main.tf) pins the Cloudflare provider and uses a `terraform_data` placeholder so `terraform init`, `fmt`, and `validate` run cleanly in CI without creating real cloud resources.

## Files in this directory

| File | Role |
|------|------|
| [main.tf](main.tf) | `required_providers`, Cloudflare provider block, `terraform_data` placeholder resource |

## Prerequisites

- [Terraform](https://www.terraform.io/) 1.5+
- Cloudflare API token with appropriate permissions (store in env, never commit)

## Commands

```bash
cd infra
export CLOUDFLARE_API_TOKEN="***"   # or use TF_VAR_cloudflare_api_token
export TF_VAR_cloudflare_account_id="your-account-id"

terraform init
terraform plan
# terraform apply   # when real resources replace the placeholder
```

## Local vs cloud shape

- **Local**: Wrangler / Miniflare for the Worker; Docker on the host for sandboxes.
- **Cloud**: Same Worker code with deployed URLs and secrets supplied through Wrangler/Terraform variables.

Document any **intentional** differences (e.g. no outbound network in prod sandboxes) in [`../sandbox/README.md`](../sandbox/README.md) and [`../control-plane/README.md`](../control-plane/README.md).
