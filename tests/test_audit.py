from datetime import UTC, datetime

import pytest

from ingestion_poc.adapters.audit import IngestionAuditReceipt, LocalAuditSink
from ingestion_poc.models import LandingRecord, VendorChangeEvent


def _receipt(event_id: str) -> IngestionAuditReceipt:
    event = VendorChangeEvent(
        event_id=event_id,
        vendor="domx",
        event_type="record.changed",
        vendor_record_id=f"domx-{event_id}",
        occurred_at=datetime.now(UTC),
        correlation_id=f"corr-{event_id}",
    )
    record = LandingRecord(
        event_id=event_id,
        vendor="domx",
        vendor_record_id=f"domx-{event_id}",
        customer_name="Customer",
        status="updated",
        amount=100.0,
        source_updated_at=datetime.now(UTC),
        extracted_at=datetime.now(UTC),
        correlation_id=f"corr-{event_id}",
    )
    return IngestionAuditReceipt.from_ingestion(event, record, "postgres")


@pytest.mark.asyncio
async def test_local_audit_sink_flushes_at_batch_threshold(tmp_path) -> None:
    sink = LocalAuditSink(batch_min_messages=2, audit_dir=str(tmp_path))

    assert await sink.record_ingestion(_receipt("event-1")) is None
    path = await sink.record_ingestion(_receipt("event-2"))

    assert path is not None
    audit_file = tmp_path / path.split("/")[-1]
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "event-1" in lines[0]
    assert "event-2" in lines[1]
