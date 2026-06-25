#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/gcp/common.sh"

load_deploy_env "$@"
write_tfvars
ensure_state_bucket
init_terraform

echo "Destroying all Terraform-managed Domx ingestion POC resources..."
terraform -chdir="$TF_DIR" destroy -auto-approve -var-file="$TFVARS"
echo "Killswitch complete."
