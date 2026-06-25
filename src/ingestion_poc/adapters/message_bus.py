from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from google.api_core.exceptions import DeadlineExceeded
from google.cloud import pubsub_v1

from ingestion_poc.config import AppConfig
from ingestion_poc.models import VendorChangeEvent

logger = logging.getLogger(__name__)


AckFn = Callable[[], Awaitable[None]]


@dataclass
class IncomingEvent:
    event: VendorChangeEvent
    ack: AckFn
    nack: AckFn


class MessageBus:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def publish(self, event: VendorChangeEvent) -> None:
        raise NotImplementedError

    async def subscribe(self) -> AsyncIterator[IncomingEvent]:
        raise NotImplementedError


class KafkaMessageBus(MessageBus):
    def __init__(self, config: AppConfig):
        self._config = config
        self._producer: AIOKafkaProducer | None = None
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._config.kafka_bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )
        await self._start_with_retry(self._producer.start, "Kafka producer")

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()
        if self._producer is not None:
            await self._producer.stop()

    async def publish(self, event: VendorChangeEvent) -> None:
        if self._producer is None:
            await self.start()
        assert self._producer is not None
        await self._producer.send_and_wait(
            self._config.kafka_topic,
            event.model_dump(mode="json"),
            key=event.vendor_record_id.encode("utf-8"),
        )
        logger.info(
            "published event_id=%s vendor_record_id=%s topic=%s",
            event.event_id,
            event.vendor_record_id,
            self._config.kafka_topic,
        )

    async def subscribe(self) -> AsyncIterator[IncomingEvent]:
        self._consumer = AIOKafkaConsumer(
            self._config.kafka_topic,
            bootstrap_servers=self._config.kafka_bootstrap_servers,
            group_id=self._config.kafka_group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        )
        await self._start_with_retry(self._consumer.start, "Kafka consumer")

        async for message in self._consumer:
            event = VendorChangeEvent.model_validate(message.value)

            async def ack() -> None:
                assert self._consumer is not None
                await self._consumer.commit()

            async def nack() -> None:
                logger.warning("nack requested for event_id=%s", event.event_id)

            yield IncomingEvent(event=event, ack=ack, nack=nack)

    async def _start_with_retry(self, start_fn: Callable[[], Awaitable[None]], name: str) -> None:
        last_error: Exception | None = None
        for attempt in range(1, 31):
            try:
                await start_fn()
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "%s not ready yet attempt=%s bootstrap_servers=%s",
                    name,
                    attempt,
                    self._config.kafka_bootstrap_servers,
                )
                await asyncio.sleep(2)
        assert last_error is not None
        raise last_error


class PubSubMessageBus(MessageBus):
    def __init__(self, config: AppConfig):
        if not config.gcp_project_id:
            raise ValueError("GCP_PROJECT_ID is required when MESSAGE_BUS=pubsub")
        self._config = config
        self._publisher = pubsub_v1.PublisherClient()
        self._subscriber = pubsub_v1.SubscriberClient()
        self._topic_path = self._publisher.topic_path(
            config.gcp_project_id, config.pubsub_topic_id
        )
        self._subscription_path = self._subscriber.subscription_path(
            config.gcp_project_id, config.pubsub_subscription_id
        )

    async def publish(self, event: VendorChangeEvent) -> None:
        payload = json.dumps(event.model_dump(mode="json")).encode("utf-8")
        future = self._publisher.publish(
            self._topic_path,
            payload,
            vendor=event.vendor,
            event_type=event.event_type,
        )
        message_id = await asyncio.to_thread(future.result)
        logger.info(
            "published event_id=%s vendor_record_id=%s pubsub_message_id=%s",
            event.event_id,
            event.vendor_record_id,
            message_id,
        )

    async def subscribe(self) -> AsyncIterator[IncomingEvent]:
        while True:
            try:
                response = await asyncio.to_thread(
                    self._subscriber.pull,
                    request={
                        "subscription": self._subscription_path,
                        "max_messages": 1,
                    },
                    timeout=30,
                )
            except DeadlineExceeded:
                await asyncio.sleep(1)
                continue
            if not response.received_messages:
                await asyncio.sleep(1)
                continue

            received = response.received_messages[0]
            event = VendorChangeEvent.model_validate_json(received.message.data)

            async def ack() -> None:
                await asyncio.to_thread(
                    self._subscriber.acknowledge,
                    request={
                        "subscription": self._subscription_path,
                        "ack_ids": [received.ack_id],
                    },
                )

            async def nack() -> None:
                await asyncio.to_thread(
                    self._subscriber.modify_ack_deadline,
                    request={
                        "subscription": self._subscription_path,
                        "ack_ids": [received.ack_id],
                        "ack_deadline_seconds": 0,
                    },
                )

            yield IncomingEvent(event=event, ack=ack, nack=nack)


def decode_pubsub_push_payload(body: dict[str, Any]) -> VendorChangeEvent:
    message = body.get("message", {})
    data = message.get("data")
    if not data:
        raise ValueError("Pub/Sub push payload missing message.data")
    decoded = base64.b64decode(data).decode("utf-8")
    return VendorChangeEvent.model_validate_json(decoded)
