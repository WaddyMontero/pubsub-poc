from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from google.cloud import storage
from pydantic import BaseModel

from ingestion_poc.config import AppConfig
from ingestion_poc.models import LandingRecord, VendorChangeEvent

logger = logging.getLogger(__name__)


class IngestionAuditReceipt(BaseModel):
    event_id: str
    vendor: str
    event_type: str
    vendor_record_id: str
    correlation_id: str
    occurred_at: datetime
    extracted_at: datetime
    audited_at: datetime
    warehouse_sink: str

    @classmethod
    def from_ingestion(
        cls,
        event: VendorChangeEvent,
        landing_record: LandingRecord,
        warehouse_sink: str,
    ) -> "IngestionAuditReceipt":
        return cls(
            event_id=event.event_id,
            vendor=event.vendor,
            event_type=event.event_type,
            vendor_record_id=event.vendor_record_id,
            correlation_id=event.correlation_id,
            occurred_at=event.occurred_at,
            extracted_at=landing_record.extracted_at,
            audited_at=datetime.now(UTC),
            warehouse_sink=warehouse_sink,
        )


class AuditSink:
    def __init__(self, batch_min_messages: int):
        self._batch_min_messages = batch_min_messages
        self._buffer: list[IngestionAuditReceipt] = []
        self._lock = asyncio.Lock()

    async def record_ingestion(self, receipt: IngestionAuditReceipt) -> str | None:
        if self._batch_min_messages <= 0:
            return None

        async with self._lock:
            self._buffer.append(receipt)
            if len(self._buffer) < self._batch_min_messages:
                logger.info(
                    "audit receipt buffered event_id=%s buffered=%s threshold=%s",
                    receipt.event_id,
                    len(self._buffer),
                    self._batch_min_messages,
                )
                return None

            batch = self._buffer
            self._buffer = []

        return await self._write_batch(batch)

    async def _write_batch(self, batch: list[IngestionAuditReceipt]) -> str:
        raise NotImplementedError


class NullAuditSink(AuditSink):
    def __init__(self) -> None:
        super().__init__(batch_min_messages=0)

    async def record_ingestion(self, receipt: IngestionAuditReceipt) -> str | None:
        return None

    async def _write_batch(self, batch: list[IngestionAuditReceipt]) -> str:
        return ""


class LocalAuditSink(AuditSink):
    def __init__(self, batch_min_messages: int, audit_dir: str):
        super().__init__(batch_min_messages)
        self._audit_dir = Path(audit_dir)

    async def _write_batch(self, batch: list[IngestionAuditReceipt]) -> str:
        return await asyncio.to_thread(self._write_batch_sync, batch)

    def _write_batch_sync(self, batch: list[IngestionAuditReceipt]) -> str:
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        path = self._audit_dir / _batch_object_name(batch)
        payload = _jsonl(batch)
        path.write_text(payload, encoding="utf-8")
        logger.info("audit batch written records=%s path=%s", len(batch), path)
        return str(path)


class GcsAuditSink(AuditSink):
    def __init__(self, batch_min_messages: int, bucket_name: str):
        if not bucket_name:
            raise ValueError("AUDIT_GCS_BUCKET is required when AUDIT_SINK=gcs")
        super().__init__(batch_min_messages)
        self._client = storage.Client()
        self._bucket_name = bucket_name

    async def _write_batch(self, batch: list[IngestionAuditReceipt]) -> str:
        return await asyncio.to_thread(self._write_batch_sync, batch)

    def _write_batch_sync(self, batch: list[IngestionAuditReceipt]) -> str:
        bucket = self._client.bucket(self._bucket_name)
        object_name = f"ingestion-audit/{_batch_object_name(batch)}"
        blob = bucket.blob(object_name)
        blob.upload_from_string(_jsonl(batch), content_type="application/x-ndjson")
        uri = f"gs://{self._bucket_name}/{object_name}"
        logger.info("audit batch written records=%s uri=%s", len(batch), uri)
        return uri


def create_audit_sink(config: AppConfig) -> AuditSink:
    if config.audit_sink == "none":
        return NullAuditSink()
    if config.audit_sink == "local":
        return LocalAuditSink(config.audit_batch_min_messages, config.audit_local_dir)
    if config.audit_sink == "gcs":
        return GcsAuditSink(config.audit_batch_min_messages, config.audit_gcs_bucket)
    raise ValueError(f"Unsupported AUDIT_SINK={config.audit_sink}")


def _batch_object_name(batch: list[IngestionAuditReceipt]) -> str:
    first = batch[0].audited_at.strftime("%Y%m%dT%H%M%SZ")
    return f"{first}-{uuid4().hex}.jsonl"


def _jsonl(batch: list[IngestionAuditReceipt]) -> str:
    return "\n".join(json.dumps(item.model_dump(mode="json")) for item in batch) + "\n"
