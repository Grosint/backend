from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.orchestrators.phone_lookup_orchestrator import (
    PhoneLookupOrchestrator,
)

logger = logging.getLogger(__name__)


class PhoneLookupAdapter(OSINTAdapter):
    """Adapter for Phone Number Lookup APIs - ViewCaller, TrueCaller, Eyecon, CallApp, WhatsApp"""

    def __init__(self):
        super().__init__()
        self.name = "PhoneLookupAdapter"
        self.orchestrator = PhoneLookupOrchestrator()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using the phone lookup orchestrator"""
        try:
            logger.info(f"PhoneLookupAdapter: Searching {country_code}{phone}")

            # Use the orchestrator to handle all phone lookup services
            result = await self.orchestrator.search_phone(country_code, phone)

            return self.normalize_success_response(result)

        except Exception as e:
            logger.error(f"PhoneLookupAdapter search failed: {e}")
            return self.normalize_error_response(e)
