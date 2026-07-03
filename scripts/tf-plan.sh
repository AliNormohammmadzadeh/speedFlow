#!/bin/bash
# Offline `terraform plan` for the SpeedFlow infra (no real AWS creds/state).
# Produces the full MSK/EKS/RDS/ElastiCache resource graph for review/CI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TFDIR="$ROOT/infra/terraform"
ENV="${1:-dev}"

cd "$TFDIR"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-west-1}"
export TF_VAR_db_password="${TF_VAR_db_password:-offline-plan-pw}"

cleanup() {
  [ -f /tmp/backend.tf.bak ] && mv /tmp/backend.tf.bak "$TFDIR/backend.tf" 2>/dev/null || true
  rm -f "$TFDIR/providers_override.tf"
  rm -rf "$TFDIR/.terraform" "$TFDIR/.terraform.lock.hcl"
}
trap cleanup EXIT

# Temporarily disable the S3 backend + inject offline provider creds.
mv backend.tf /tmp/backend.tf.bak
cat > providers_override.tf <<'EOF'
provider "aws" {
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}
EOF

rm -rf .terraform .terraform.lock.hcl
terraform init -backend=false -input=false >/dev/null
terraform plan -var-file="environments/${ENV}.tfvars" -input=false -no-color
