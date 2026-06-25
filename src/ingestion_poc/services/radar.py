from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status

from ingestion_poc.adapters.message_bus import MessageBus
from ingestion_poc.config import load_config
from ingestion_poc.factory import create_message_bus
from ingestion_poc.logging import configure_logging
from ingestion_poc.models import VendorChangeEvent, VendorWebhookPayload

config = load_config()
configure_logging(config.service_name)
logger = logging.getLogger(__name__)

bus: MessageBus


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bus
    bus = create_message_bus(config)
    await bus.start()
    logger.info("radar started vendor=%s message_bus=%s", config.vendor_name, config.message_bus)
    try:
        yield
    finally:
        await bus.stop()


app = FastAPI(title="Vendor Radar", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "radar"}


@app.post("/webhooks/{vendor}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(
    vendor: str,
    request: Request,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    if config.webhook_secret and x_webhook_secret != config.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    if vendor.lower() != config.vendor_name.lower():
        raise HTTPException(status_code=404, detail=f"Unsupported vendor: {vendor}")

    raw = await request.json()
    webhook = VendorWebhookPayload.model_validate(raw)
    event = VendorChangeEvent.from_webhook(config.vendor_name, webhook, raw)
    logger.info(
        "webhook received vendor=%s vendor_record_id=%s event_type=%s",
        event.vendor,
        event.vendor_record_id,
        event.event_type,
    )
    await bus.publish(event)
    return {
        "accepted": True,
        "event_id": event.event_id,
        "correlation_id": event.correlation_id,
    }
