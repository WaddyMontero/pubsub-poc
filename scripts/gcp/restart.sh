#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

load_deploy_env "$@"
write_tfvars
ensure_state_bucket
init_terraform

RESTARTED_AT="$(date -u +%Y%m%dT%H%M%SZ)"

for service in radar extractor mock-vendor-api; do
  gcloud run services update "${NAME_PREFIX}-${service}" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --update-env-vars "RESTARTED_AT=${RESTARTED_AT}" \
    --quiet
done

if [[ "${RUN_SMOKE_TEST:-1}" == "1" ]]; then
  "$ROOT_DIR/scripts/gcp/smoke_test.sh"
fi
