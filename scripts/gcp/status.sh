#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/gcp/common.sh"

load_deploy_env "$@"
write_tfvars
ensure_state_bucket
init_terraform

echo "Cloud Run services"
gcloud run services list --project "$PROJECT_ID" --region "$REGION" --filter="metadata.name~domx-ingestion-poc"

echo
echo "Cloud Run jobs"
gcloud run jobs list --project "$PROJECT_ID" --region "$REGION" --filter="metadata.name~domx-ingestion-poc"

echo
echo "Terraform outputs"
terraform -chdir="$TF_DIR" output
