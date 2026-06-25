#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/gcp/common.sh"

RUN_SMOKE_TEST="${RUN_SMOKE_TEST:-1}"

load_deploy_env "$@"
write_tfvars
ensure_state_bucket

echo "Initializing Terraform..."
init_terraform

echo "Creating required APIs and Artifact Registry repository..."
terraform -chdir="$TF_DIR" apply \
  -auto-approve \
  -var-file="$TFVARS" \
  -target=google_project_service.required \
  -target=google_artifact_registry_repository.images

echo "Building and pushing image: $IMAGE_URI"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker buildx build --platform linux/amd64 -t "$IMAGE_URI" --push "$ROOT_DIR"

echo "Applying full Terraform deployment..."
terraform -chdir="$TF_DIR" apply -auto-approve -var-file="$TFVARS"

echo
terraform -chdir="$TF_DIR" output

if [[ "$RUN_SMOKE_TEST" == "1" ]]; then
  "$ROOT_DIR/scripts/gcp/smoke_test.sh"
fi

echo
echo "Killswitch: ./scripts/gcp/killswitch.sh"
