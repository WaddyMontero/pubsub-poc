from __future__ import annotations

import asyncio
import logging
from typing import Any

import psycopg
from google.cloud import bigquery

from ingestion_poc.config import AppConfig
from ingestion_poc.models import LandingRecord

logger = logging.getLogger(__name__)


class WarehouseSink:
    async def start(self) -> None:
        return None

    async def write_landing_record(self, record: LandingRecord) -> bool:
        raise NotImplementedError


class PostgresWarehouseSink(WarehouseSink):
    def __init__(self, config: AppConfig):
        self._dsn = config.postgres_dsn

    async def start(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, 31):
            try:
                await asyncio.to_thread(self._ensure_table)
                return
            except Exception as exc:
                last_error = exc
                logger.warning("Postgres not ready yet attempt=%s", attempt)
                await asyncio.sleep(2)
        assert last_error is not None
        raise last_error

    def _ensure_table(self) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                create table if not exists landing_records (
                    event_id text primary key,
                    vendor text not null,
                    vendor_record_id text not null,
                    customer_name text not null,
                    status text not null,
                    amount numeric not null,
                    source_updated_at timestamptz not null,
                    extracted_at timestamptz not null,
                    correlation_id text not null
                )
                """
            )
            conn.execute(
                """
                create index if not exists idx_landing_records_vendor_record
                on landing_records (vendor, vendor_record_id)
                """
            )

    async def write_landing_record(self, record: LandingRecord) -> bool:
        inserted = await asyncio.to_thread(self._insert, record)
        if inserted:
            logger.info(
                "wrote landing record event_id=%s vendor_record_id=%s sink=postgres",
                record.event_id,
                record.vendor_record_id,
            )
        else:
            logger.info(
                "ignored duplicate event_id=%s vendor_record_id=%s sink=postgres",
                record.event_id,
                record.vendor_record_id,
            )
        return inserted

    def _insert(self, record: LandingRecord) -> bool:
        with psycopg.connect(self._dsn) as conn:
            cursor = conn.execute(
                """
                insert into landing_records (
                    event_id,
                    vendor,
                    vendor_record_id,
                    customer_name,
                    status,
                    amount,
                    source_updated_at,
                    extracted_at,
                    correlation_id
                )
                values (
                    %(event_id)s,
                    %(vendor)s,
                    %(vendor_record_id)s,
                    %(customer_name)s,
                    %(status)s,
                    %(amount)s,
                    %(source_updated_at)s,
                    %(extracted_at)s,
                    %(correlation_id)s
                )
                on conflict (event_id) do nothing
                """,
                record.model_dump(),
            )
            return cursor.rowcount == 1


class BigQueryWarehouseSink(WarehouseSink):
    def __init__(self, config: AppConfig):
        if not config.gcp_project_id:
            raise ValueError("GCP_PROJECT_ID is required when WAREHOUSE_SINK=bigquery")
        self._client = bigquery.Client(project=config.gcp_project_id)
        self._table_id = (
            f"{config.gcp_project_id}.{config.bigquery_dataset}.{config.bigquery_table}"
        )

    async def write_landing_record(self, record: LandingRecord) -> bool:
        row = record.model_dump(mode="json")
        errors = await asyncio.to_thread(
            self._client.insert_rows_json,
            self._table_id,
            [row],
            row_ids=[record.event_id],
        )
        if errors:
            raise RuntimeError(f"BigQuery insert failed: {errors}")
        logger.info(
            "wrote landing record event_id=%s vendor_record_id=%s sink=bigquery",
            record.event_id,
            record.vendor_record_id,
        )
        return True


class InMemoryWarehouseSink(WarehouseSink):
    def __init__(self) -> None:
        self.records: dict[str, LandingRecord] = {}

    async def write_landing_record(self, record: LandingRecord) -> bool:
        if record.event_id in self.records:
            return False
        self.records[record.event_id] = record
        return True


def bigquery_schema() -> list[bigquery.SchemaField]:
    return [
        bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("vendor", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("vendor_record_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("customer_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("amount", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("source_updated_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("correlation_id", "STRING", mode="REQUIRED"),
    ]


def landing_record_table_sql() -> str:
    return """
    create table if not exists landing_records (
        event_id text primary key,
        vendor text not null,
        vendor_record_id text not null,
        customer_name text not null,
        status text not null,
        amount numeric not null,
        source_updated_at timestamptz not null,
        extracted_at timestamptz not null,
        correlation_id text not null
    );
    """
