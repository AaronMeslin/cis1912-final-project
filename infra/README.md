# `infra/` — Terraform (Cloudflare + future providers)

## What this component is

This directory holds **Infrastructure as Code** for the platform: primarily **Cloudflare** (Workers, DNS, optional KV/D1) and, later, whatever runs **Docker** sandboxes at scale (VMs, Kubernetes, Nomad—TBD). The current [`main.tf`](main.tf) is a **stub**: it pins the Cloudflare provider and uses a `terraform_data` placeholder so `terraform init` / `plan` can run without creating real cloud resources.

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

## Environment parity (local vs cloud)

- **Local**: Wrangler / Miniflare for the Worker; Docker on the host for sandboxes.
- **Cloud**: Same Worker code deployed via CI; sandboxes on managed compute; secrets via Wrangler/Terraform variables.

Document any **intentional** differences (e.g. no outbound network in prod sandboxes) in [`../sandbox/README.md`](../sandbox/README.md) and [`../control-plane/README.md`](../control-plane/README.md).

## Tasks to implement

- [ ] Remote state backend (S3, GCS, Terraform Cloud) with locking
- [ ] `cloudflare_worker` or documented Wrangler + Terraform split of responsibilities
- [ ] DNS records and custom domains for the control plane API
- [ ] KV/D1/R2 buckets if used for sandbox metadata or artifacts
- [ ] Infra for Docker hosts (ASG, k8s cluster, or dedicated servers) matching sandbox image
- [ ] Variables for staging vs production; no secrets in `.tf` files
