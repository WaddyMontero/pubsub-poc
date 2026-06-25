# GitHub Actions Deployment

This repo includes manual GitHub Actions for operating the GCP demo:

- `CI`: runs unit tests and Terraform validation.
- `Deploy GCP`: builds the container, applies Terraform, and optionally runs the 15-message smoke test.
- `Restart GCP`: bumps a Cloud Run environment variable to roll the radar, extractor, and mock vendor API revisions, then optionally runs the smoke test.
- `Destroy GCP`: guarded killswitch that only runs when the confirmation input matches `destroy PROJECT_ID`.

The workflows use GitHub OIDC with GCP Workload Identity Federation. No long-lived GCP key is stored in GitHub.

## One-Time Bootstrap

After the GitHub repository exists, run:

```bash
PROJECT_ID="pubsub-poc-500520" \
GITHUB_REPOSITORY="OWNER/REPO" \
./scripts/gcp/bootstrap_github_actions_auth.sh
```

The script creates:

- A Workload Identity pool and OIDC provider restricted to that GitHub repository.
- A `github-actions-deployer` service account.
- Project IAM grants needed by Terraform, Cloud Run, Artifact Registry, Pub/Sub, BigQuery, and GCS.
- Service account impersonation grants for GitHub Actions.
- GitHub repository secrets:
  - `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - `GCP_SERVICE_ACCOUNT`

## Operating The Demo

Use the GitHub Actions UI and run workflows manually with these defaults:

```text
project_id: pubsub-poc-500520
region: europe-west1
generator_count: 15
audit_batch_min_messages: 15
run_smoke_test: true
```

For teardown, run `Destroy GCP` and type:

```text
destroy pubsub-poc-500520
```
