from __future__ import annotations

import random
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from ingestion_poc.config import load_config
from ingestion_poc.logging import configure_logging
from ingestion_poc.models import VendorRecord, VendorWebhookPayload

config = load_config()
configure_logging(config.service_name)

app = FastAPI(title="Mock Vendor API")

records: dict[str, VendorRecord] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock_vendor_api"}


@app.post("/simulate-change")
async def simulate_change() -> VendorWebhookPayload:
    vendor_record_id = f"domx-{uuid4().hex[:10]}"
    customer_number = random.randint(1000, 9999)
    record = VendorRecord(
        vendor_record_id=vendor_record_id,
        customer_name=f"Customer {customer_number}",
        status=random.choice(["created", "updated", "review_required", "approved"]),
        amount=round(random.uniform(100, 25000), 2),
        updated_at=datetime.now(UTC),
        source_payload={
            "vendor": config.vendor_name,
            "synthetic": True,
            "customer_number": customer_number,
        },
    )
    records[vendor_record_id] = record
    return VendorWebhookPayload(
        vendor_record_id=vendor_record_id,
        event_type="record.changed",
        occurred_at=record.updated_at,
        payload_ref=f"/records/{vendor_record_id}",
        correlation_id=str(uuid4()),
    )


@app.get("/records/{vendor_record_id}")
async def get_record(vendor_record_id: str) -> VendorRecord:
    record = records.get(vendor_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
