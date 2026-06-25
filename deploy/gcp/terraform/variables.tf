variable "project_id" {
  description = "GCP project ID to deploy the POC into."
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run and Artifact Registry."
  type        = string
  default     = "europe-west1"
}

variable "bigquery_location" {
  description = "BigQuery dataset location."
  type        = string
  default     = "EU"
}

variable "name_prefix" {
  description = "Prefix used for GCP resource names."
  type        = string
  default     = "domx-ingestion-poc"
}

variable "vendor_name" {
  description = "Synthetic vendor name used in the POC."
  type        = string
  default     = "domx"
}

variable "image_uri" {
  description = "Container image URI pushed to Artifact Registry."
  type        = string
}

variable "generator_count" {
  description = "Number of synthetic changes generated per Cloud Run Job execution."
  type        = number
  default     = 15
}

variable "generator_interval_seconds" {
  description = "Delay between synthetic changes in the generator job."
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Maximum instances for radar and extractor."
  type        = number
  default     = 3
}

variable "cloud_run_min_instances" {
  description = "Minimum warm instances for always-on Cloud Run services. Use 0 for scale-to-zero cost optimization."
  type        = number
  default     = 1
}

variable "audit_batch_min_messages" {
  description = "Minimum successfully ingested messages per audit proof file."
  type        = number
  default     = 15
}

variable "extractor_max_instances" {
  description = "Maximum extractor instances. Defaults to one so audit batching is deterministic for the POC."
  type        = number
  default     = 1
}

variable "labels" {
  description = "Labels applied to supported resources."
  type        = map(string)
  default = {
    app       = "domx-ingestion-poc"
    managedby = "terraform"
    purpose   = "demo"
  }
}
