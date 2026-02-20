"""Virtual number lookup adapter using NumCheckr."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.integrations.virtual_number.numcheckr_service import NumCheckrService

logger = logging.getLogger(__name__)


class VirtualNumberAdapter(OSINTAdapter):
    """Adapter for virtual/throwaway number verification via NumCheckr."""

    def __init__(self):
        super().__init__()
        self.name = "VirtualNumberAdapter"
        self.service = NumCheckrService()

    async def search_virtual_number(
        self, phone_number: str, country_code: str = "+91"
    ) -> dict[str, Any]:
        """Check if phone number is virtual."""
        try:
            logger.info(f"VirtualNumberAdapter: Checking {phone_number}")

            result = await self.service.check_number(phone_number, country_code)

            combined = {
                "lookup_results": {"numcheckr": result},
                "summary": {
                    "total_sources": 1,
                    "successful_sources": 1 if result.get("found", False) else 0,
                    "found_data": result.get("found", False),
                },
            }
            return self.normalize_success_response(combined)

        except Exception as e:
            logger.error(f"VirtualNumberAdapter search failed: {e}")
            return self.normalize_error_response(e)
