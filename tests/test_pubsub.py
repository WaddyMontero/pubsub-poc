import base64
from datetime import UTC, datetime

from ingestion_poc.adapters.message_bus import decode_pubsub_push_payload
from ingestion_poc.models import VendorChangeEvent


def test_decode_pubsub_push_payload() -> None:
    event = VendorChangeEvent(
        event_id="event-123",
        vendor="domx",
        event_type="record.changed",
        vendor_record_id="domx-123",
        occurred_at=datetime.now(UTC),
        correlation_id="corr-123",
    )
    body = {
        "message": {
            "messageId": "pubsub-1",
            "data": base64.b64encode(event.model_dump_json().encode("utf-8")).decode(
                "utf-8"
            ),
        }
    }

    decoded = decode_pubsub_push_payload(body)

    assert decoded == event
