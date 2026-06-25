from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ingestion_poc.models import VendorChangeEvent, VendorWebhookPayload


def test_vendor_change_event_from_webhook_uses_trigger_fields() -> None:
    raw = {
        "vendor_record_id": "domx-123",
        "event_type": "record.changed",
        "occurred_at": "2026-06-25T10:00:00Z",
        "payload_ref": "/records/domx-123",
        "extra_vendor_field": "kept in raw webhook",
    }
    webhook = VendorWebhookPayload.model_validate(raw)

    event = VendorChangeEvent.from_webhook("domx", webhook, raw)

    assert event.schema_version == 1
    assert event.vendor == "domx"
    assert event.vendor_record_id == "domx-123"
    assert event.payload_ref == "/records/domx-123"
    assert event.raw_webhook == raw


def test_webhook_requires_record_id() -> None:
    with pytest.raises(ValidationError):
        VendorWebhookPayload.model_validate({"event_type": "record.changed"})


def test_event_round_trips_json() -> None:
    event = VendorChangeEvent(
        vendor="domx",
        event_type="record.changed",
        vendor_record_id="domx-123",
        occurred_at=datetime.now(UTC),
    )

    restored = VendorChangeEvent.model_validate_json(event.model_dump_json())

    assert restored == event
