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
AUDIT_BATCH_MIN_MESSAGES="${AUDIT_BATCH_MIN_MESSAGES:-15}"
VERIFY_ATTEMPTS="${VERIFY_ATTEMPTS:-24}"
VERIFY_SLEEP_SECONDS="${VERIFY_SLEEP_SECONDS:-5}"

count_audit_files() {
  gcloud storage ls "gs://${AUDIT_BUCKET}/ingestion-audit/**" --project "$PROJECT_ID" 2>/dev/null | wc -l | tr -d ' '
}

list_audit_files() {
  gcloud storage ls "gs://${AUDIT_BUCKET}/ingestion-audit/**" --project "$PROJECT_ID" 2>/dev/null || true
}

BEFORE_RECORDS="$(bq query \
  --project_id="$PROJECT_ID" \
  --use_legacy_sql=false \
  --format=csv \
  "select count(*) as landed_records from \`$BIGQUERY_TABLE\`" | tail -n 1)"
BEFORE_AUDIT_FILES="$(count_audit_files)"

echo "Executing generator job: $GENERATOR_JOB count=$GENERATOR_COUNT"
gcloud run jobs execute "$GENERATOR_JOB" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --update-env-vars "GENERATOR_COUNT=${GENERATOR_COUNT}" \
  --wait

echo "Checking BigQuery landing table: $BIGQUERY_TABLE"
NEW_RECORDS=0
for ((attempt = 1; attempt <= VERIFY_ATTEMPTS; attempt++)); do
  LANDED_RECORDS="$(bq query \
    --project_id="$PROJECT_ID" \
    --use_legacy_sql=false \
    --format=csv \
    "select count(*) as landed_records from \`$BIGQUERY_TABLE\`" | tail -n 1)"
  NEW_RECORDS=$((LANDED_RECORDS - BEFORE_RECORDS))
  if [[ "$NEW_RECORDS" -ge "$GENERATOR_COUNT" ]]; then
    break
  fi
  echo "Waiting for BigQuery rows attempt=$attempt before=$BEFORE_RECORDS current=$LANDED_RECORDS new=$NEW_RECORDS expected_new_at_least=$GENERATOR_COUNT"
  sleep "$VERIFY_SLEEP_SECONDS"
done

if [[ "$NEW_RECORDS" -lt "$GENERATOR_COUNT" ]]; then
  echo "Expected at least $GENERATOR_COUNT new rows, but only found $NEW_RECORDS." >&2
  exit 1
fi

bq query \
  --project_id="$PROJECT_ID" \
  --use_legacy_sql=false \
  "select count(*) as landed_records, max(extracted_at) as latest_extracted_at from \`$BIGQUERY_TABLE\`"

echo
echo "Recent GCS audit proof files:"
EXPECTED_NEW_AUDIT_FILES=$((GENERATOR_COUNT / AUDIT_BATCH_MIN_MESSAGES))
for ((attempt = 1; attempt <= VERIFY_ATTEMPTS; attempt++)); do
  list_audit_files >/tmp/domx-audit-files.txt
  AUDIT_FILE_COUNT="$(wc -l < /tmp/domx-audit-files.txt | tr -d ' ')"
  NEW_AUDIT_FILES=$((AUDIT_FILE_COUNT - BEFORE_AUDIT_FILES))
  tail -n 10 /tmp/domx-audit-files.txt
  if [[ "$EXPECTED_NEW_AUDIT_FILES" -eq 0 || "$NEW_AUDIT_FILES" -ge "$EXPECTED_NEW_AUDIT_FILES" ]]; then
    exit 0
  fi
  echo "Waiting for GCS audit proof files attempt=$attempt before=$BEFORE_AUDIT_FILES current=$AUDIT_FILE_COUNT new=$NEW_AUDIT_FILES expected_new_at_least=$EXPECTED_NEW_AUDIT_FILES"
  sleep "$VERIFY_SLEEP_SECONDS"
done

echo "Expected at least $EXPECTED_NEW_AUDIT_FILES new GCS audit proof files in gs://${AUDIT_BUCKET}/ingestion-audit/." >&2
exit 1
