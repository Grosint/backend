from __future__ import annotations

import logging
from typing import Any

from app.services.integrations.email_lookup.ghunt import GHuntService
from app.services.integrations.email_lookup.philint import PhilINTService
from app.services.integrations.phone_lookup.leakcheck_service import LeakCheckService
from app.services.integrations.phone_lookup.skype_service import SkypeService

logger = logging.getLogger(__name__)


class EmailLookupOrchestrator:
    """Orchestrator for email lookup external APIs"""

    def __init__(self):
        self.name = "EmailLookupOrchestrator"

        # Initialize all email lookup services
        self.skype_service = SkypeService()
        self.leakcheck_service = LeakCheckService()
        self.ghunt_service = GHuntService()
        self.philint_service = PhilINTService()

    async def search_email(self, email: str) -> dict[str, Any]:
        """Search email address across all email lookup services"""
        try:
            logger.info(f"EmailLookupOrchestrator: Searching {email}")

            # Call all email lookup services in parallel
            tasks = [
                self.skype_service.search_email(email),
                self.leakcheck_service.search_email(email),
                self.ghunt_service.search_email(email),
                self.philint_service.search_email(email),
            ]

            import asyncio

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            combined_data = {
                "email": email,
                "lookup_results": {},
                "summary": {
                    "total_sources": len(tasks),
                    "successful_sources": 0,
                    "found_data": False,
                },
            }

            service_names = [
                "skype",
                "leakcheck",
                "ghunt",
                "philint",
            ]
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
