from __future__ import annotations

import logging
from typing import Any

from app.services.integrations.phone_lookup.aitan_service import AITANService
from app.services.integrations.phone_lookup.befisc_service import BefiscService
from app.services.integrations.phone_lookup.callapp_service import CallAppService
from app.services.integrations.phone_lookup.eyecon_service import EyeconService
from app.services.integrations.phone_lookup.hlr_service import HLRService
from app.services.integrations.phone_lookup.ignorant_service import IgnorantService
from app.services.integrations.phone_lookup.leakcheck_service import LeakCheckService
from app.services.integrations.phone_lookup.skype_service import SkypeService
from app.services.integrations.phone_lookup.telegram_service import TelegramService
from app.services.integrations.phone_lookup.truecaller_service import TrueCallerService
from app.services.integrations.phone_lookup.viewcaller_service import ViewCallerService
from app.services.integrations.phone_lookup.whatsapp_service import WhatsAppService

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
        self.telegram_service = TelegramService()
        self.skype_service = SkypeService()
        self.ignorant_service = IgnorantService()
        self.leakcheck_service = LeakCheckService()
        self.hlr_service = HLRService()
        self.aitan_service = AITANService()
        self.befisc_service = BefiscService()

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
                self.telegram_service.search_phone(country_code, phone),
                self.ignorant_service.search_phone(country_code, phone),
                self.leakcheck_service.search_phone(country_code, phone),
                self.hlr_service.search_phone(country_code, phone),
                self.aitan_service.search_phone(country_code, phone, "phone-lookup"),
                self.befisc_service.search_phone(country_code, phone, "phone-lookup"),
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
                "telegram",
                "ignorant",
                "leakcheck",
                "hlr",
                "aitan",
                "befisc",
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

            # Extract emails from results and search Skype
            emails = self._extract_emails_from_results(results, service_names)
            if emails:
                logger.info(f"Found {len(emails)} email(s) in results, searching Skype")
                skype_results = await self._search_skype_for_emails(emails)
                if skype_results:
                    combined_data["lookup_results"]["skype"] = skype_results
                    if skype_results.get("found", False):
                        combined_data["summary"]["successful_sources"] += 1
                        combined_data["summary"]["found_data"] = True
                    combined_data["summary"]["total_sources"] += 1
            else:
                logger.info("No emails found in results, skipping Skype search")

            logger.info(
                f"PhoneLookupOrchestrator completed: {combined_data['summary']['successful_sources']}/{combined_data['summary']['total_sources']} services successful"
            )
            return combined_data

        except Exception as e:
            logger.error(f"PhoneLookupOrchestrator failed: {e}")
            raise

    def _extract_emails_from_results(
        self, results: list[Any], service_names: list[str]
    ) -> list[str]:
        """Extract email addresses from phone lookup results"""
        emails = set()
        import re

        email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        )

        for _i, result in enumerate(results):
            if isinstance(result, Exception):
                continue

            # Check if result has data field
            if isinstance(result, dict):
                data = result.get("data")
                if data:
                    # If data is a list, iterate through it
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                value = item.get("value", "")
                                # Check if value is an email
                                if (
                                    value
                                    and isinstance(value, str)
                                    and "@" in value
                                    and email_pattern.match(value)
                                ):
                                    emails.add(value.lower())
                    # If data is a dict, check for email fields
                    elif isinstance(data, dict):
                        for _key, value in data.items():
                            if isinstance(value, str) and "@" in value:
                                if email_pattern.match(value):
                                    emails.add(value.lower())
                            elif isinstance(value, list):
                                for item in value:
                                    if (
                                        isinstance(item, str)
                                        and "@" in item
                                        and email_pattern.match(item)
                                    ):
                                        emails.add(item.lower())

                # Also check raw_response for emails
                raw_response = result.get("_raw_response")
                if raw_response:
                    raw_str = str(raw_response)
                    found_emails = email_pattern.findall(raw_str)
                    for email in found_emails:
                        emails.add(email.lower())

        return list(emails)

    async def _search_skype_for_emails(self, emails: list[str]) -> dict[str, Any]:
        """Search Skype for multiple emails"""
        try:
            # Search with the first email found (can be extended to search all)
            if not emails:
                return {
                    "found": False,
                    "source": "skype",
                    "data": None,
                    "confidence": 0.0,
                    "error": "No emails provided",
                }

            # Search with all emails and combine results
            skype_tasks = [
                self.skype_service.search_email(email) for email in emails[:3]
            ]  # Limit to 3 emails to avoid too many requests

            import asyncio

            skype_results = await asyncio.gather(*skype_tasks, return_exceptions=True)

            # Combine Skype results
            combined_skype_data = []
            found_any = False

            for i, skype_result in enumerate(skype_results):
                if isinstance(skype_result, Exception):
                    logger.warning(
                        f"Skype search failed for {emails[i]}: {skype_result}"
                    )
                    continue

                if isinstance(skype_result, dict) and skype_result.get("found"):
                    found_any = True
                    data = skype_result.get("data", [])
                    if data:
                        combined_skype_data.extend(data)

            if found_any and combined_skype_data:
                return {
                    "found": True,
                    "source": "skype",
                    "data": combined_skype_data,
                    "confidence": 0.8,
                    "_raw_response": {"emails_searched": emails},
                }
            else:
                return {
                    "found": False,
                    "source": "skype",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": {"emails_searched": emails},
                }

        except Exception as e:
            logger.error(f"Skype search for emails failed: {e}")
            return {
                "found": False,
                "source": "skype",
                "data": None,
                "confidence": 0.0,
                "error": str(e),
            }
