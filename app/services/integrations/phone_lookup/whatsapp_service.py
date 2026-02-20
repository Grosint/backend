from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.lookup_extractor import extract_items
from app.core.lookup_specs import PHONE_LOOKUP_SPECS
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for WhatsApp API integration"""

    def __init__(self):
        self.name = "WhatsAppService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using WhatsApp API"""
        try:
            logger.info(f"WhatsApp: Searching {country_code}{phone}")

            country_code_clean = country_code.replace("+", "")
            url = f"https://whatsapp-data1.p.rapidapi.com/number/{country_code_clean}{phone}"

            response = await self.client.request(
                "GET",
                url,
                headers={
                    "x-rapidapi-key": settings.RAPIDAPI_KEY,
                    "x-rapidapi-host": "whatsapp-data1.p.rapidapi.com",
                },
                circuit_key="whatsapp_api",
            )

            data = response.json()
            raw_response = data  # Store raw response before processing

            if "error" in data:
                return {
                    "found": False,
                    "source": "whatsapp",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": raw_response,
                }
            else:
                # Format WhatsApp response
                formatted_data = extract_items(data, PHONE_LOOKUP_SPECS["whatsapp"])
                found = bool(
                    data.get("isUser")
                    or data.get("isWAContact")
                    or data.get("phone")
                    or data.get("number")
                )
                return {
                    "found": found,
                    "source": "whatsapp",
                    "data": formatted_data,
                    "confidence": 0.9 if found else 0.0,
                    "_raw_response": raw_response,
                }
        except Exception as e:
            logger.error(f"WhatsApp search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "error": str(e),
                "_raw_response": raw_response,
            }
