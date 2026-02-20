"""IMEI lookup adapter using Kelpom IMEI Checker."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.integrations.imei_lookup.kelpom_service import KelpomIMEIService

logger = logging.getLogger(__name__)


class IMEILookupAdapter(OSINTAdapter):
    """Adapter for IMEI device lookup via Kelpom RapidAPI."""

    def __init__(self):
        super().__init__()
        self.name = "IMEILookupAdapter"
        self.service = KelpomIMEIService()

    async def search_imei(self, imei: str) -> dict[str, Any]:
        """Search IMEI for device details."""
        try:
            logger.info(f"IMEILookupAdapter: Searching {imei}")

            result = await self.service.search_imei(imei)

            combined = {
                "lookup_results": {"kelpom_imei": result},
                "summary": {
                    "total_sources": 1,
                    "successful_sources": 1 if result.get("found", False) else 0,
                    "found_data": result.get("found", False),
                },
            }
            return self.normalize_success_response(combined)

        except Exception as e:
            logger.error(f"IMEILookupAdapter search failed: {e}")
            return self.normalize_error_response(e)
