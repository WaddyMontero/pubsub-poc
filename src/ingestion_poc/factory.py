from __future__ import annotations

from ingestion_poc.adapters.message_bus import KafkaMessageBus, MessageBus, PubSubMessageBus
from ingestion_poc.adapters.sinks import (
    BigQueryWarehouseSink,
    PostgresWarehouseSink,
    WarehouseSink,
)
from ingestion_poc.config import AppConfig


def create_message_bus(config: AppConfig) -> MessageBus:
    if config.message_bus == "kafka":
        return KafkaMessageBus(config)
    if config.message_bus == "pubsub":
        return PubSubMessageBus(config)
    raise ValueError(f"Unsupported MESSAGE_BUS={config.message_bus}")


def create_warehouse_sink(config: AppConfig) -> WarehouseSink:
    if config.warehouse_sink == "postgres":
        return PostgresWarehouseSink(config)
    if config.warehouse_sink == "bigquery":
        return BigQueryWarehouseSink(config)
    raise ValueError(f"Unsupported WAREHOUSE_SINK={config.warehouse_sink}")
