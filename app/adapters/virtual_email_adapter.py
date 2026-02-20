"""Virtual email lookup adapter using Email Intelligence API."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.integrations.virtual_email.email_intelligence_service import (
    EmailIntelligenceService,
)

logger = logging.getLogger(__name__)


class VirtualEmailAdapter(OSINTAdapter):
    """Adapter for virtual/disposable email detection via Email Intelligence API."""

    def __init__(self):
        super().__init__()
        self.name = "VirtualEmailAdapter"
        self.service = EmailIntelligenceService()

    async def search_virtual_email(self, email: str) -> dict[str, Any]:
        """Check if email is virtual/disposable."""
        try:
            logger.info(f"VirtualEmailAdapter: Checking {email}")

            result = await self.service.check_email(email)

            combined = {
                "lookup_results": {"email_intelligence": result},
                "summary": {
                    "total_sources": 1,
                    "successful_sources": 1 if result.get("found", False) else 0,
                    "found_data": result.get("found", False),
                },
            }
            return self.normalize_success_response(combined)

        except Exception as e:
            logger.error(f"VirtualEmailAdapter search failed: {e}")
            return self.normalize_error_response(e)
