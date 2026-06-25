from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class VendorWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    vendor_record_id: str = Field(min_length=1)
    event_type: str = Field(default="record.changed", min_length=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload_ref: str | None = None
    correlation_id: str | None = None


class VendorChangeEvent(BaseModel):
    schema_version: int = 1
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    vendor: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    vendor_record_id: str = Field(min_length=1)
    occurred_at: datetime
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    payload_ref: str | None = None
    raw_webhook: dict[str, Any] | None = None

    @classmethod
    def from_webhook(
        cls, vendor: str, payload: VendorWebhookPayload, raw_webhook: dict[str, Any]
    ) -> "VendorChangeEvent":
        return cls(
            vendor=vendor,
            event_type=payload.event_type,
            vendor_record_id=payload.vendor_record_id,
            occurred_at=payload.occurred_at,
            correlation_id=payload.correlation_id or str(uuid4()),
            payload_ref=payload.payload_ref,
            raw_webhook=raw_webhook,
        )


class VendorRecord(BaseModel):
    vendor_record_id: str
    customer_name: str
    status: str
    amount: float
    updated_at: datetime
    source_payload: dict[str, Any] = Field(default_factory=dict)


class LandingRecord(BaseModel):
    event_id: str
    vendor: str
    vendor_record_id: str
    customer_name: str
    status: str
    amount: float
    source_updated_at: datetime
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str
