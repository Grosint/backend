"""Bank account lookup adapter using Befisc."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.integrations.phone_lookup.befisc_service import BefiscService

logger = logging.getLogger(__name__)


class BankLookupAdapter(OSINTAdapter):
    """Adapter for bank account verification via Befisc."""

    def __init__(self):
        super().__init__()
        self.name = "BankLookupAdapter"
        self.befisc = BefiscService()

    async def search_bank(
        self,
        account_no: str | None = None,
        ifsc_code: str | None = None,
        upi: str | None = None,
    ) -> dict[str, Any]:
        """Search bank info by account+IFSC or UPI."""
        try:
            logger.info("BankLookupAdapter: Searching bank info")

            if account_no and ifsc_code:
                result = await self.befisc._bank_search(account_no, ifsc_code)
            elif upi:
                result = await self.befisc._upi_search(upi)
            else:
                result = {
                    "found": False,
                    "source": "befisc",
                    "error": "Either (account_no and ifsc_code) or upi required",
                    "confidence": 0.0,
                }

            combined = self._to_lookup_format(result, "befisc")
            return self.normalize_success_response(combined)

        except Exception as e:
            logger.error(f"BankLookupAdapter search failed: {e}")
            return self.normalize_error_response(e)

    def _to_lookup_format(self, result: dict[str, Any], source: str) -> dict[str, Any]:
        """Convert service result to lookup_results format."""
        return {
            "lookup_results": {source: result},
            "summary": {
                "total_sources": 1,
                "successful_sources": 1 if result.get("found", False) else 0,
                "found_data": result.get("found", False),
            },
        }
