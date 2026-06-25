data "google_project" "current" {
  project_id = var.project_id
}

locals {
  service_prefix         = var.name_prefix
  repository_id          = "${var.name_prefix}-images"
  pubsub_topic_id        = "${var.name_prefix}-change-events"
  pubsub_subscription_id = "${var.name_prefix}-extractor-push"
  bigquery_dataset_id    = replace(var.name_prefix, "-", "_")
  bigquery_table_id      = "landing_records"
  audit_bucket_name      = "${var.project_id}-${var.name_prefix}-audit"
  pubsub_service_agent   = "service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "iam.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = local.repository_id
  description   = "Container images for the Domx ingestion POC"
  format        = "DOCKER"
  labels        = var.labels

  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-recent-demo-images"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "radar" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-radar"
  display_name = "Domx ingestion POC radar"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "extractor" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-extractor"
  display_name = "Domx ingestion POC extractor"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "generator" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-generator"
  display_name = "Domx ingestion POC generator"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "pubsub_push" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-push"
  display_name = "Domx ingestion POC Pub/Sub push invoker"

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic" "change_events" {
  project = var.project_id
  name    = local.pubsub_topic_id
  labels  = var.labels

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic_iam_member" "radar_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.change_events.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.radar.email}"
}

resource "google_bigquery_dataset" "landing" {
  project                    = var.project_id
  dataset_id                 = local.bigquery_dataset_id
  friendly_name              = "Domx ingestion POC"
  description                = "Landing dataset for the event-driven ingestion POC."
  location                   = var.bigquery_location
  labels                     = var.labels
  delete_contents_on_destroy = true

  depends_on = [google_project_service.required]
}

resource "google_bigquery_table" "landing_records" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.landing.dataset_id
  table_id            = local.bigquery_table_id
  deletion_protection = false
  labels              = var.labels

  time_partitioning {
    type  = "DAY"
    field = "extracted_at"
  }

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "vendor", type = "STRING", mode = "REQUIRED" },
    { name = "vendor_record_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_name", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "amount", type = "FLOAT", mode = "REQUIRED" },
    { name = "source_updated_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "extracted_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "correlation_id", type = "STRING", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_dataset_iam_member" "extractor_writer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.landing.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.extractor.email}"
}

resource "google_storage_bucket" "audit" {
  project                     = var.project_id
  name                        = local.audit_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
  labels                      = var.labels

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "extractor_audit_writer" {
  bucket = google_storage_bucket.audit.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.extractor.email}"
}

resource "google_cloud_run_v2_service" "mock_vendor_api" {
  project             = var.project_id
  name                = "${local.service_prefix}-mock-vendor-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = var.labels

  scaling {
    min_instance_count = var.cloud_run_min_instances
    scaling_mode       = "AUTOMATIC"
  }

  template {
    service_account = google_service_account.generator.email
    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = 1
    }

    containers {
      image   = var.image_uri
      command = ["uvicorn"]
      args    = ["ingestion_poc.services.mock_vendor_api:app", "--host", "0.0.0.0", "--port", "8080"]

      ports {
        container_port = 8080
      }

      env {
        name  = "SERVICE_NAME"
        value = "mock_vendor_api"
      }
      env {
        name  = "VENDOR_NAME"
        value = var.vendor_name
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "radar" {
  project             = var.project_id
  name                = "${local.service_prefix}-radar"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = var.labels

  scaling {
    min_instance_count = var.cloud_run_min_instances
    scaling_mode       = "AUTOMATIC"
  }

  template {
    service_account = google_service_account.radar.email
    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image   = var.image_uri
      command = ["uvicorn"]
      args    = ["ingestion_poc.services.radar:app", "--host", "0.0.0.0", "--port", "8080"]

      ports {
        container_port = 8080
      }

      env {
        name  = "SERVICE_NAME"
        value = "radar"
      }
      env {
        name  = "VENDOR_NAME"
        value = var.vendor_name
      }
      env {
        name  = "MESSAGE_BUS"
        value = "pubsub"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "PUBSUB_TOPIC_ID"
        value = google_pubsub_topic.change_events.name
      }
    }
  }

  depends_on = [google_pubsub_topic_iam_member.radar_publisher]
}

resource "google_cloud_run_v2_service" "extractor" {
  project             = var.project_id
  name                = "${local.service_prefix}-extractor"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = var.labels

  scaling {
    min_instance_count = var.cloud_run_min_instances
    scaling_mode       = "AUTOMATIC"
  }

  template {
    service_account = google_service_account.extractor.email
    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.extractor_max_instances
    }

    containers {
      image   = var.image_uri
      command = ["python"]
      args    = ["-m", "ingestion_poc.services.extractor", "api", "--port", "8080"]

      ports {
        container_port = 8080
      }

      env {
        name  = "SERVICE_NAME"
        value = "extractor"
      }
      env {
        name  = "VENDOR_NAME"
        value = var.vendor_name
      }
      env {
        name  = "WAREHOUSE_SINK"
        value = "bigquery"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = google_bigquery_dataset.landing.dataset_id
      }
      env {
        name  = "BIGQUERY_TABLE"
        value = google_bigquery_table.landing_records.table_id
      }
      env {
        name  = "VENDOR_API_URL"
        value = google_cloud_run_v2_service.mock_vendor_api.uri
      }
      env {
        name  = "AUDIT_SINK"
        value = "gcs"
      }
      env {
        name  = "AUDIT_BATCH_MIN_MESSAGES"
        value = tostring(var.audit_batch_min_messages)
      }
      env {
        name  = "AUDIT_GCS_BUCKET"
        value = google_storage_bucket.audit.name
      }
    }
  }

  depends_on = [
    google_bigquery_dataset_iam_member.extractor_writer,
    google_storage_bucket_iam_member.extractor_audit_writer,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "radar_public" {
  project  = var.project_id
  location = google_cloud_run_v2_service.radar.location
  name     = google_cloud_run_v2_service.radar.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "mock_vendor_public" {
  project  = var.project_id
  location = google_cloud_run_v2_service.mock_vendor_api.location
  name     = google_cloud_run_v2_service.mock_vendor_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "pubsub_can_invoke_extractor" {
  project  = var.project_id
  location = google_cloud_run_v2_service.extractor.location
  name     = google_cloud_run_v2_service.extractor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_push.email}"
}

resource "google_service_account_iam_member" "pubsub_can_mint_oidc" {
  service_account_id = google_service_account.pubsub_push.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${local.pubsub_service_agent}"

  depends_on = [google_project_service.required]
}

resource "google_pubsub_subscription" "extractor_push" {
  project = var.project_id
  name    = local.pubsub_subscription_id
  topic   = google_pubsub_topic.change_events.name
  labels  = var.labels

  ack_deadline_seconds       = 30
  message_retention_duration = "1200s"

  expiration_policy {
    ttl = ""
  }

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.extractor.uri}/pubsub/push"

    oidc_token {
      service_account_email = google_service_account.pubsub_push.email
      audience              = google_cloud_run_v2_service.extractor.uri
    }
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.pubsub_can_invoke_extractor,
    google_service_account_iam_member.pubsub_can_mint_oidc,
  ]
}

resource "google_cloud_run_v2_job" "generator" {
  project             = var.project_id
  name                = "${local.service_prefix}-generator"
  location            = var.region
  deletion_protection = false
  labels              = var.labels

  template {
    template {
      service_account = google_service_account.generator.email
      max_retries     = 1
      timeout         = "600s"

      containers {
        image   = var.image_uri
        command = ["python"]
        args    = ["-m", "ingestion_poc.services.generator"]

        env {
          name  = "SERVICE_NAME"
          value = "generator"
        }
        env {
          name  = "VENDOR_NAME"
          value = var.vendor_name
        }
        env {
          name  = "RADAR_URL"
          value = google_cloud_run_v2_service.radar.uri
        }
        env {
          name  = "VENDOR_API_URL"
          value = google_cloud_run_v2_service.mock_vendor_api.uri
        }
        env {
          name  = "GENERATOR_COUNT"
          value = tostring(var.generator_count)
        }
        env {
          name  = "GENERATOR_INTERVAL_SECONDS"
          value = tostring(var.generator_interval_seconds)
        }
      }
    }
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.radar_public,
    google_cloud_run_v2_service_iam_member.mock_vendor_public,
    google_pubsub_subscription.extractor_push,
  ]
}
