output "artifact_registry_repository" {
  value       = google_artifact_registry_repository.images.name
  description = "Artifact Registry repository resource name."
}

output "image_uri" {
  value       = var.image_uri
  description = "Container image URI used by Cloud Run."
}

output "radar_url" {
  value       = google_cloud_run_v2_service.radar.uri
  description = "Public radar webhook base URL."
}

output "mock_vendor_api_url" {
  value       = google_cloud_run_v2_service.mock_vendor_api.uri
  description = "Public mock vendor API base URL."
}

output "extractor_url" {
  value       = google_cloud_run_v2_service.extractor.uri
  description = "Extractor Cloud Run URL. It is invoked by Pub/Sub, not public users."
}

output "generator_job_name" {
  value       = google_cloud_run_v2_job.generator.name
  description = "Cloud Run Job that generates synthetic Domx changes."
}

output "pubsub_topic" {
  value       = google_pubsub_topic.change_events.name
  description = "Pub/Sub topic receiving normalized vendor change events."
}

output "bigquery_table" {
  value       = "${var.project_id}.${google_bigquery_dataset.landing.dataset_id}.${google_bigquery_table.landing_records.table_id}"
  description = "BigQuery landing table."
}

output "audit_bucket" {
  value       = google_storage_bucket.audit.name
  description = "GCS bucket containing JSONL ingestion audit proof files."
}

output "killswitch_command" {
  value       = "./scripts/gcp/killswitch.sh"
  description = "Command to destroy all Terraform-managed GCP POC resources."
}
