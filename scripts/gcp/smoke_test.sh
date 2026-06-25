#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/gcp/common.sh"

load_deploy_env "$@"
write_tfvars
ensure_state_bucket
init_terraform

GENERATOR_JOB="$(terraform -chdir="$TF_DIR" output -raw generator_job_name)"
BIGQUERY_TABLE="$(terraform -chdir="$TF_DIR" output -raw bigquery_table)"
AUDIT_BUCKET="$(terraform -chdir="$TF_DIR" output -raw audit_bucket)"
GENERATOR_COUNT="${GENERATOR_COUNT:-15}"

echo "Executing generator job: $GENERATOR_JOB"
gcloud run jobs execute "$GENERATOR_JOB" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --wait

echo "Checking BigQuery landing table: $BIGQUERY_TABLE"
for attempt in {1..12}; do
  LANDED_RECORDS="$(bq query \
    --project_id="$PROJECT_ID" \
    --use_legacy_sql=false \
    --format=csv \
    "select count(*) as landed_records from \`$BIGQUERY_TABLE\`" | tail -n 1)"
  if [[ "$LANDED_RECORDS" -ge "$GENERATOR_COUNT" ]]; then
    break
  fi
  echo "Waiting for BigQuery rows attempt=$attempt landed_records=$LANDED_RECORDS expected_at_least=$GENERATOR_COUNT"
  sleep 5
done

bq query \
  --project_id="$PROJECT_ID" \
  --use_legacy_sql=false \
  "select count(*) as landed_records, max(extracted_at) as latest_extracted_at from \`$BIGQUERY_TABLE\`"

echo
echo "Recent GCS audit proof files:"
for attempt in {1..12}; do
  if gcloud storage ls "gs://${AUDIT_BUCKET}/ingestion-audit/**" --project "$PROJECT_ID" >/tmp/domx-audit-files.txt 2>/dev/null; then
    tail -n 10 /tmp/domx-audit-files.txt
    exit 0
  fi
  echo "Waiting for GCS audit proof file attempt=$attempt"
  sleep 5
done

echo "No GCS audit proof file found in gs://${AUDIT_BUCKET}/ingestion-audit/" >&2
exit 1
