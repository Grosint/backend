from __future__ import annotations

import logging
from typing import Any

from app.external_apis.phone_lookup.callapp_service import CallAppService
from app.external_apis.phone_lookup.eyecon_service import EyeconService
from app.external_apis.phone_lookup.truecaller_service import TrueCallerService
from app.external_apis.phone_lookup.viewcaller_service import ViewCallerService
from app.external_apis.phone_lookup.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class PhoneLookupOrchestrator:
    """Orchestrator for phone lookup external APIs"""

    def __init__(self):
        self.name = "PhoneLookupOrchestrator"

        # Initialize all phone lookup services
        self.viewcaller_service = ViewCallerService()
        self.truecaller_service = TrueCallerService()
        self.eyecon_service = EyeconService()
        self.callapp_service = CallAppService()
        self.whatsapp_service = WhatsAppService()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number across all phone lookup services"""
        try:
            logger.info(f"PhoneLookupOrchestrator: Searching {country_code}{phone}")

            # Call all phone lookup services in parallel
            tasks = [
                self.viewcaller_service.search_phone(country_code, phone),
                self.truecaller_service.search_phone(country_code, phone),
                self.eyecon_service.search_phone(country_code, phone),
                self.callapp_service.search_phone(country_code, phone),
                self.whatsapp_service.search_phone(country_code, phone),
            ]

            import asyncio

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            combined_data = {
                "phone": f"{country_code}{phone}",
                "lookup_results": {},
                "summary": {
                    "total_sources": len(tasks),
                    "successful_sources": 0,
                    "found_data": False,
                },
            }

            service_names = [
                "viewcaller",
                "truecaller",
                "eyecon",
                "callapp",
                "whatsapp",
            ]
            for i, result in enumerate(results):
                service_name = service_names[i]
                if isinstance(result, Exception):
                    combined_data["lookup_results"][service_name] = {
                        "error": str(result)
                    }
                    logger.error(
                        f"Phone lookup service {service_name} failed: {result}"
                    )
                else:
                    combined_data["lookup_results"][service_name] = result
                    if result.get("found", False):
                        combined_data["summary"]["successful_sources"] += 1
                        combined_data["summary"]["found_data"] = True

            logger.info(
                f"PhoneLookupOrchestrator completed: {combined_data['summary']['successful_sources']}/{combined_data['summary']['total_sources']} services successful"
            )
            return combined_data

        except Exception as e:
            logger.error(f"PhoneLookupOrchestrator failed: {e}")
            raise
