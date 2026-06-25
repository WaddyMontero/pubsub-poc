from __future__ import annotations

import argparse
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status

from ingestion_poc.adapters.audit import AuditSink, IngestionAuditReceipt, create_audit_sink
from ingestion_poc.adapters.message_bus import (
    MessageBus,
    decode_pubsub_push_payload,
)
from ingestion_poc.adapters.sinks import WarehouseSink
from ingestion_poc.adapters.vendor import VendorClient, VendorRecordNotFoundError
from ingestion_poc.config import AppConfig, load_config
from ingestion_poc.factory import create_message_bus, create_warehouse_sink
from ingestion_poc.logging import configure_logging
from ingestion_poc.models import LandingRecord, VendorChangeEvent

config = load_config()
configure_logging(config.service_name)
logger = logging.getLogger(__name__)

sink: WarehouseSink
audit_sink: AuditSink
vendor_client: VendorClient


async def process_event(
    event: VendorChangeEvent,
    vendor_api: VendorClient,
    warehouse_sink: WarehouseSink,
    ingestion_audit_sink: AuditSink | None = None,
    warehouse_sink_name: str = "warehouse",
) -> bool:
    logger.info(
        "event consumed event_id=%s vendor_record_id=%s",
        event.event_id,
        event.vendor_record_id,
    )
    vendor_record = await vendor_api.fetch_record(event.vendor_record_id)
    landing_record = LandingRecord(
        event_id=event.event_id,
        vendor=event.vendor,
        vendor_record_id=vendor_record.vendor_record_id,
        customer_name=vendor_record.customer_name,
        status=vendor_record.status,
        amount=vendor_record.amount,
        source_updated_at=vendor_record.updated_at,
        extracted_at=datetime.now(UTC),
        correlation_id=event.correlation_id,
    )
    inserted = await warehouse_sink.write_landing_record(landing_record)
    if inserted and ingestion_audit_sink is not None:
        receipt = IngestionAuditReceipt.from_ingestion(
            event,
            landing_record,
            warehouse_sink_name,
        )
        await ingestion_audit_sink.record_ingestion(receipt)
    return inserted


async def run_worker(app_config: AppConfig) -> None:
    bus: MessageBus = create_message_bus(app_config)
    warehouse_sink = create_warehouse_sink(app_config)
    ingestion_audit_sink = create_audit_sink(app_config)
    vendor_api = VendorClient(app_config.vendor_api_url)

    await bus.start()
    await warehouse_sink.start()
    logger.info(
        "extractor worker started message_bus=%s sink=%s audit_sink=%s audit_batch_min_messages=%s",
        app_config.message_bus,
        app_config.warehouse_sink,
        app_config.audit_sink,
        app_config.audit_batch_min_messages,
    )
    try:
        async for incoming in bus.subscribe():
            try:
                await process_event(
                    incoming.event,
                    vendor_api,
                    warehouse_sink,
                    ingestion_audit_sink,
                    app_config.warehouse_sink,
                )
                await incoming.ack()
            except VendorRecordNotFoundError:
                logger.exception(
                    "vendor record missing event_id=%s vendor_record_id=%s",
                    incoming.event.event_id,
                    incoming.event.vendor_record_id,
                )
                await incoming.nack()
            except Exception:
                logger.exception("failed to process event_id=%s", incoming.event.event_id)
                await incoming.nack()
                await asyncio.sleep(2)
    finally:
        await vendor_api.close()
        await bus.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sink, audit_sink, vendor_client
    sink = create_warehouse_sink(config)
    audit_sink = create_audit_sink(config)
    vendor_client = VendorClient(config.vendor_api_url)
    await sink.start()
    logger.info(
        "extractor API started sink=%s audit_sink=%s audit_batch_min_messages=%s",
        config.warehouse_sink,
        config.audit_sink,
        config.audit_batch_min_messages,
    )
    try:
        yield
    finally:
        await vendor_client.close()


app = FastAPI(title="Vendor Extractor", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "extractor"}


@app.post("/pubsub/push", status_code=status.HTTP_204_NO_CONTENT)
async def pubsub_push(request: Request) -> None:
    body: dict[str, Any] = await request.json()
    try:
        event = decode_pubsub_push_payload(body)
        await process_event(event, vendor_client, sink, audit_sink, config.warehouse_sink)
    except Exception as exc:
        logger.exception("failed to process Pub/Sub push payload")
        raise HTTPException(status_code=500, detail="processing failed") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the vendor extractor.")
    parser.add_argument("mode", choices=["worker", "api"], help="worker consumes from bus; api accepts Pub/Sub push")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8080, type=int)
    args = parser.parse_args()

    if args.mode == "worker":
        asyncio.run(run_worker(config))
    else:
        uvicorn.run(
            "ingestion_poc.services.extractor:app",
            host=args.host,
            port=args.port,
            log_config=None,
        )


if __name__ == "__main__":
    main()
