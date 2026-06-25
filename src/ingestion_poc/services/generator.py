from __future__ import annotations

import asyncio
import logging

import httpx

from ingestion_poc.config import load_config
from ingestion_poc.logging import configure_logging

config = load_config()
configure_logging(config.service_name)
logger = logging.getLogger(__name__)


async def wait_for_endpoint(client: httpx.AsyncClient, url: str, name: str) -> None:
    for attempt in range(1, 31):
        try:
            response = await client.get(url)
            if response.status_code == 200:
                logger.info("%s is ready", name)
                return
        except httpx.RequestError:
            pass
        logger.info("waiting for %s attempt=%s", name, attempt)
        await asyncio.sleep(2)
    raise RuntimeError(f"{name} did not become ready")


async def generate_once(client: httpx.AsyncClient) -> None:
    vendor_response = await client.post(f"{config.vendor_api_url.rstrip('/')}/simulate-change")
    vendor_response.raise_for_status()
    webhook_payload = vendor_response.json()

    radar_response = await client.post(
        f"{config.radar_url.rstrip('/')}/webhooks/{config.vendor_name}",
        json=webhook_payload,
    )
    radar_response.raise_for_status()
    radar_result = radar_response.json()
    logger.info(
        "generated change vendor_record_id=%s event_id=%s",
        webhook_payload["vendor_record_id"],
        radar_result["event_id"],
    )


async def main_async() -> None:
    count = 0
    async with httpx.AsyncClient(timeout=10) as client:
        await wait_for_endpoint(
            client,
            f"{config.vendor_api_url.rstrip('/')}/health",
            "mock vendor API",
        )
        await wait_for_endpoint(
            client,
            f"{config.radar_url.rstrip('/')}/health",
            "radar",
        )
        while config.generator_count == 0 or count < config.generator_count:
            try:
                await generate_once(client)
                count += 1
            except httpx.HTTPError as exc:
                logger.warning("generator request failed; retrying error=%s", exc)
            except Exception:
                logger.exception("generator failed unexpectedly; retrying")
            await asyncio.sleep(config.generator_interval_seconds)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
