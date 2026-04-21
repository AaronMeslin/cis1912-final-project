# Sandboxed Agent Execution Platform — Terraform root (stub).
# TODO: Add remote backend (S3 + DynamoDB, Terraform Cloud, etc.) for state.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
    # TODO: Add docker / kubernetes / fly provider when orchestration target is chosen.
  }
}

# TODO: Set via `export CLOUDFLARE_API_TOKEN=...` or `TF_VAR_cloudflare_api_token`
variable "cloudflare_api_token" {
  type        = string
  description = "Cloudflare API token with Workers permissions (set via env, not committed)"
  sensitive   = true
  default     = ""
}

variable "cloudflare_account_id" {
  type        = string
  description = "Cloudflare account ID"
  default     = ""
}

provider "cloudflare" {
  # api_token pulled from CLOUDFLARE_API_TOKEN when variable is empty
  api_token = var.cloudflare_api_token != "" ? var.cloudflare_api_token : null
}

# Placeholder: real Workers deployment often uses wrangler/ci or cloudflare_worker resource.
# TODO: Replace with cloudflare_worker_script or Wrangler-driven deploy + Terraform for DNS only.

resource "terraform_data" "saep_placeholder" {
  # Stub so `terraform plan` can run after init without creating cloud resources.
  input = "scaffold-1"
}

output "placeholder" {
  value       = "TODO: wire Cloudflare Worker + sandbox infra"
  description = "Replace with meaningful outputs (worker URL, cluster endpoint, etc.)"
}
