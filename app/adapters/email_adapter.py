from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.orchestrators.email_lookup_orchestrator import (
    EmailLookupOrchestrator,
)

logger = logging.getLogger(__name__)


class EmailAdapter(OSINTAdapter):
    """Adapter for email-related OSINT operations"""

    def __init__(self):
        super().__init__()
        self.name = "EmailAdapter"
        self.orchestrator = EmailLookupOrchestrator()

    async def search_email(self, email: str) -> dict[str, Any]:
        """
        Search for information about an email using multiple sources

        Args:
            email: Email address to search for

        Returns:
            dict: Combined results from multiple sources
        """
        try:
            logger.info(f"EmailAdapter: Searching {email}")

            # Use the orchestrator to handle all email lookup services
            result = await self.orchestrator.search_email(email)

            return self.normalize_success_response(result)

        except Exception as e:
            logger.error(f"EmailAdapter search failed: {e}")
            return self.normalize_error_response(e)
