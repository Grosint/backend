"""Email Intelligence API (RapidAPI) - virtual/disposable email detection."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class EmailIntelligenceService:
    """Service for email intelligence - temp/virtual email detection via RapidAPI."""

    def __init__(self):
        self.name = "EmailIntelligenceService"
        self.client = ResilientHttpClient()
        self.base_url = "https://email-intelligence-api.p.rapidapi.com/v1/check"

    async def check_email(self, email: str) -> dict[str, Any]:
        """Check email for provider, temp email, validity, etc."""
        try:
            logger.info(f"EmailIntelligence: Checking {email}")

            headers = {
                "x-rapidapi-key": settings.RAPIDAPI_KEY,
                "x-rapidapi-host": "email-intelligence-api.p.rapidapi.com",
            }
            params = {"email": email}

            response = await self.client.request(
                "GET",
                self.base_url,
                params=params,
                headers=headers,
                circuit_key="email_intelligence",
            )

            data = response.json()
            raw_response = data

            if data and "error" not in data:
                formatted = self._process_email_intel_response(data)
                return {
                    "found": True,
                    "source": "email_intelligence",
                    "data": formatted,
                    "confidence": 0.8,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "source": "email_intelligence",
                    "data": None,
                    "confidence": 0.0,
                    "error": (
                        data.get("message", "No data")
                        if isinstance(data, dict)
                        else "Invalid response"
                    ),
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"EmailIntelligence check failed: {e}")
            return {
                "found": False,
                "source": "email_intelligence",
                "error": str(e),
                "confidence": 0.0,
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    def _process_email_intel_response(self, result: dict[str, Any]) -> dict[str, Any]:
        """Process email intelligence API response."""
        data = result.get("data", {})
        email = data.get("email", "Not Found")
        email_provider = data.get("email_provider", {})
        is_edu = data.get("is_edu", False)
        is_gov = data.get("is_gov", False)
        is_temp_email = data.get("is_temp_email", False)
        is_valid = data.get("is_valid", False)
        records = data.get("records", {})
        summary = data.get("summary", [])
        website_data = data.get("website_data", {})

        def get_summary_value(key: str) -> str:
            for item in summary:
                if isinstance(item, dict) and key in item:
                    return str(item.get(key, "Not Found"))
            return "Not Found"

        return {
            "data": {
                "Email": email,
                "provider": (
                    email_provider.get("provider", "Not Found")
                    if isinstance(email_provider, dict)
                    else "Not Found"
                ),
                "is_edu": is_edu,
                "Is_gov": is_gov,
                "Is_temp_email": is_temp_email,
                "is_valid": is_valid,
            },
            "email_records": {
                "DMARC": (
                    records.get("dmarc", "Not Found")
                    if isinstance(records, dict)
                    else "Not Found"
                ),
                "SPF": (
                    records.get("spf", "Not Found")
                    if isinstance(records, dict)
                    else "Not Found"
                ),
                "DKIM": get_summary_value("DKIM"),
                "MX": get_summary_value("MX"),
                "TXT": get_summary_value("TXT"),
                "DMARC_status": get_summary_value("DMARC"),
            },
            "website_data": {
                "is_valid": (
                    website_data.get("is_valid", False)
                    if isinstance(website_data, dict)
                    else False
                ),
                "SSL": (
                    website_data.get("ssl", "Not Found")
                    if isinstance(website_data, dict)
                    else "Not Found"
                ),
                "website_domain": (
                    website_data.get("website_domain", "Not Found")
                    if isinstance(website_data, dict)
                    else "Not Found"
                ),
                "status": result.get("status", "Not Found"),
            },
        }
