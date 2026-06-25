#!/usr/bin/env bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/deploy/gcp/terraform"
DEPLOY_ENV="$ROOT_DIR/.gcp-deployment.env"

load_deploy_env() {
  if [[ -f "$DEPLOY_ENV" ]]; then
    # shellcheck disable=SC1090
    source "$DEPLOY_ENV"
  fi

  PROJECT_ID="${PROJECT_ID:-${1:-}}"
  REGION="${REGION:-europe-west1}"
  NAME_PREFIX="${NAME_PREFIX:-domx-ingestion-poc}"
  GENERATOR_COUNT="${GENERATOR_COUNT:-15}"
  AUDIT_BATCH_MIN_MESSAGES="${AUDIT_BATCH_MIN_MESSAGES:-15}"
  TF_STATE_BUCKET="${TF_STATE_BUCKET:-${PROJECT_ID}-${NAME_PREFIX}-tfstate}"
  TF_STATE_PREFIX="${TF_STATE_PREFIX:-terraform/state}"

  if [[ -z "$PROJECT_ID" ]]; then
    echo "PROJECT_ID is required." >&2
    exit 1
  fi

  IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${NAME_PREFIX}-images/${NAME_PREFIX}:latest"
  TFVARS="$TF_DIR/terraform.tfvars"
}

write_tfvars() {
  cat > "$TFVARS" <<EOF
project_id  = "$PROJECT_ID"
region      = "$REGION"
name_prefix = "$NAME_PREFIX"
image_uri   = "$IMAGE_URI"
generator_count = $GENERATOR_COUNT
audit_batch_min_messages = $AUDIT_BATCH_MIN_MESSAGES
EOF

  cat > "$DEPLOY_ENV" <<EOF
PROJECT_ID="$PROJECT_ID"
REGION="$REGION"
NAME_PREFIX="$NAME_PREFIX"
IMAGE_URI="$IMAGE_URI"
GENERATOR_COUNT="$GENERATOR_COUNT"
AUDIT_BATCH_MIN_MESSAGES="$AUDIT_BATCH_MIN_MESSAGES"
TF_STATE_BUCKET="$TF_STATE_BUCKET"
TF_STATE_PREFIX="$TF_STATE_PREFIX"
EOF
}

ensure_state_bucket() {
  gcloud services enable storage.googleapis.com --project "$PROJECT_ID" --quiet

  if ! gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "Creating Terraform state bucket: gs://${TF_STATE_BUCKET}"
    gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
      --project "$PROJECT_ID" \
      --location "$REGION" \
      --uniform-bucket-level-access
  fi
}

init_terraform() {
  local migrate_args=()
  if [[ -f "$TF_DIR/terraform.tfstate" ]]; then
    migrate_args=(-migrate-state -force-copy)
  fi

  terraform -chdir="$TF_DIR" init \
    -input=false \
    -backend-config="bucket=${TF_STATE_BUCKET}" \
    -backend-config="prefix=${TF_STATE_PREFIX}" \
    "${migrate_args[@]}"
}
