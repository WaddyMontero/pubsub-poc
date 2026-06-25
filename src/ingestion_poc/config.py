from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


@dataclass(frozen=True)
class AppConfig:
    service_name: str = "poc"
    vendor_name: str = "domx"

    message_bus: str = "kafka"
    warehouse_sink: str = "postgres"
    audit_sink: str = "none"
    audit_batch_min_messages: int = 15

    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_topic: str = "vendor.change-events"
    kafka_group_id: str = "domxtractor"

    gcp_project_id: str = ""
    pubsub_topic_id: str = "vendor-change-events"
    pubsub_subscription_id: str = "vendor-change-events-extractor"

    postgres_dsn: str = "postgresql://poc:poc@localhost:5432/poc"
    bigquery_dataset: str = "vendor_ingestion_poc"
    bigquery_table: str = "landing_records"
    audit_gcs_bucket: str = ""
    audit_local_dir: str = "/tmp/ingestion_audit"

    vendor_api_url: str = "http://localhost:8001"
    radar_url: str = "http://localhost:8000"
    webhook_secret: str = ""

    generator_interval_seconds: float = 3.0
    generator_count: int = 10


def load_config() -> AppConfig:
    return AppConfig(
        service_name=os.getenv("SERVICE_NAME", "poc"),
        vendor_name=os.getenv("VENDOR_NAME", "domx"),
        message_bus=os.getenv("MESSAGE_BUS", "kafka").lower(),
        warehouse_sink=os.getenv("WAREHOUSE_SINK", "postgres").lower(),
        audit_sink=os.getenv("AUDIT_SINK", "none").lower(),
        audit_batch_min_messages=_int_env("AUDIT_BATCH_MIN_MESSAGES", 15),
        kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"),
        kafka_topic=os.getenv("KAFKA_TOPIC", "vendor.change-events"),
        kafka_group_id=os.getenv("KAFKA_GROUP_ID", "domxtractor"),
        gcp_project_id=os.getenv("GCP_PROJECT_ID", ""),
        pubsub_topic_id=os.getenv("PUBSUB_TOPIC_ID", "vendor-change-events"),
        pubsub_subscription_id=os.getenv(
            "PUBSUB_SUBSCRIPTION_ID", "vendor-change-events-extractor"
        ),
        postgres_dsn=os.getenv("POSTGRES_DSN", "postgresql://poc:poc@localhost:5432/poc"),
        bigquery_dataset=os.getenv("BIGQUERY_DATASET", "vendor_ingestion_poc"),
        bigquery_table=os.getenv("BIGQUERY_TABLE", "landing_records"),
        audit_gcs_bucket=os.getenv("AUDIT_GCS_BUCKET", ""),
        audit_local_dir=os.getenv("AUDIT_LOCAL_DIR", "/tmp/ingestion_audit"),
        vendor_api_url=os.getenv("VENDOR_API_URL", "http://localhost:8001"),
        radar_url=os.getenv("RADAR_URL", "http://localhost:8000"),
        webhook_secret=os.getenv("WEBHOOK_SECRET", ""),
        generator_interval_seconds=_float_env("GENERATOR_INTERVAL_SECONDS", 3.0),
        generator_count=_int_env("GENERATOR_COUNT", 10),
    )
