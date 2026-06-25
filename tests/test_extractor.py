from datetime import UTC, datetime

import pytest

from ingestion_poc.adapters.sinks import InMemoryWarehouseSink
from ingestion_poc.models import VendorChangeEvent, VendorRecord
from ingestion_poc.services.extractor import process_event


class FakeVendorClient:
    def __init__(self, record: VendorRecord):
        self.record = record
        self.fetches: list[str] = []

    async def fetch_record(self, vendor_record_id: str) -> VendorRecord:
        self.fetches.append(vendor_record_id)
        return self.record


class FakeAuditSink:
    def __init__(self):
        self.receipts = []

    async def record_ingestion(self, receipt):
        self.receipts.append(receipt)
        return None


@pytest.mark.asyncio
async def test_process_event_fetches_vendor_record_and_writes_sink() -> None:
    record = VendorRecord(
        vendor_record_id="domx-123",
        customer_name="Customer 123",
        status="updated",
        amount=250.50,
        updated_at=datetime.now(UTC),
    )
    vendor = FakeVendorClient(record)
    sink = InMemoryWarehouseSink()
    audit = FakeAuditSink()
    event = VendorChangeEvent(
        event_id="event-123",
        vendor="domx",
        event_type="record.changed",
        vendor_record_id="domx-123",
        occurred_at=datetime.now(UTC),
        correlation_id="corr-123",
    )

    inserted = await process_event(event, vendor, sink, audit, "postgres")

    assert inserted is True
    assert vendor.fetches == ["domx-123"]
    assert sink.records["event-123"].customer_name == "Customer 123"
    assert sink.records["event-123"].correlation_id == "corr-123"
    assert audit.receipts[0].event_id == "event-123"
    assert audit.receipts[0].warehouse_sink == "postgres"


@pytest.mark.asyncio
async def test_process_event_is_idempotent_by_event_id() -> None:
    record = VendorRecord(
        vendor_record_id="domx-123",
        customer_name="Customer 123",
        status="updated",
        amount=250.50,
        updated_at=datetime.now(UTC),
    )
    vendor = FakeVendorClient(record)
    sink = InMemoryWarehouseSink()
    audit = FakeAuditSink()
    event = VendorChangeEvent(
        event_id="event-123",
        vendor="domx",
        event_type="record.changed",
        vendor_record_id="domx-123",
        occurred_at=datetime.now(UTC),
        correlation_id="corr-123",
    )

    assert await process_event(event, vendor, sink, audit, "postgres") is True
    assert await process_event(event, vendor, sink, audit, "postgres") is False

    assert len(sink.records) == 1
    assert len(audit.receipts) == 1
