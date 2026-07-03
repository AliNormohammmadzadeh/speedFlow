# Remote state backend. Configured per-environment at init time, e.g.:
#   terraform init -backend-config=environments/dev.backend.hcl
# Use `terraform init -backend=false` for offline `terraform validate`.
terraform {
  backend "s3" {}
}
