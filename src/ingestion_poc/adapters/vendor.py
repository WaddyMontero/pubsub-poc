from __future__ import annotations

import logging

import httpx

from ingestion_poc.models import VendorRecord

logger = logging.getLogger(__name__)


class VendorRecordNotFoundError(RuntimeError):
    pass


class VendorClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=10)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_record(self, vendor_record_id: str) -> VendorRecord:
        response = await self._client.get(f"{self._base_url}/records/{vendor_record_id}")
        if response.status_code == 404:
            raise VendorRecordNotFoundError(vendor_record_id)
        response.raise_for_status()
        record = VendorRecord.model_validate(response.json())
        logger.info("fetched vendor_record_id=%s from vendor API", vendor_record_id)
        return record
