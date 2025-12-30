from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.integrations.email_lookup.ghunt import GHuntService
from app.services.integrations.email_lookup.holehe import HoleheService
from app.services.integrations.email_lookup.philint import PhilINTService
from app.services.integrations.phone_lookup.leakcheck_service import LeakCheckService

logger = logging.getLogger(__name__)


class EmailLookupOrchestrator:
    """Orchestrator for email lookup external APIs"""

    def __init__(self):
        self.name = "EmailLookupOrchestrator"

        # Initialize all email lookup services
        self.ghunt_service = GHuntService()
        self.holehe_service = HoleheService()
        self.philint_service = PhilINTService()
        self.leakcheck_service = LeakCheckService()

    async def search_email(self, email: str) -> dict[str, Any]:
        """Search email address across all email lookup services

        Args:
            email: Email address to search for

        Returns:
            dict: Combined results from all email lookup services
        """
        try:
            logger.info(f"EmailLookupOrchestrator: Searching {email}")

            # Check if email is Gmail to conditionally include GHunt
            is_gmail = email.lower().endswith("@gmail.com")
            if is_gmail:
                logger.info(
                    "EmailLookupOrchestrator: Gmail detected, including GHunt service"
                )

            # Build tasks list - only include GHunt for Gmail accounts
            tasks = []
            service_names = []

            if is_gmail:
                tasks.append(self.ghunt_service.search_email(email))
                service_names.append("ghunt")

            # Always include these services
            tasks.append(self.holehe_service.search_email(email))
            service_names.append("holehe")

            tasks.append(self.philint_service.search_email(email))
            service_names.append("philint")

            tasks.append(self.leakcheck_service.search_email(email))
            service_names.append("leakcheck")

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            combined_data: dict[str, Any] = {
                "email": email,
                "lookup_results": {},
                "summary": {
                    "total_sources": len(tasks),
                    "successful_sources": 0,
                    "found_data": False,
                },
            }

            for i, result in enumerate(results):
                service_name = service_names[i]
                if isinstance(result, Exception):
                    combined_data["lookup_results"][service_name] = {
                        "error": str(result)
                    }
                    logger.error(
                        f"Email lookup service {service_name} failed: {result}"
                    )
                else:
                    combined_data["lookup_results"][service_name] = result
                    if result.get("found", False):
                        combined_data["summary"]["successful_sources"] += 1
                        combined_data["summary"]["found_data"] = True

            logger.info(
                f"EmailLookupOrchestrator completed: {combined_data['summary']['successful_sources']}/{combined_data['summary']['total_sources']} services successful"
            )
            return combined_data

        except Exception as e:
            logger.error(f"EmailLookupOrchestrator failed: {e}")
            raise
