from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.lookup_extractor import extract_items
from app.core.lookup_specs import PHONE_LOOKUP_SPECS
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class ViewCallerService:
    """Service for ViewCaller API integration"""

    def __init__(self):
        self.name = "ViewCallerService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using ViewCaller API"""
        try:
            logger.info(f"ViewCaller: Searching {country_code}{phone}")

            # Remove '+' from country_code if present, as API expects integer
            country_code_clean = (
                country_code.lstrip("+")
                if country_code.startswith("+")
                else country_code
            )

            response = await self.client.request(
                "GET",
                "https://viewcaller.p.rapidapi.com/api/v1/search",
                params={"code": country_code_clean, "number": phone},
                headers={
                    "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                    "X-RapidAPI-Host": "viewcaller.p.rapidapi.com",
                },
                circuit_key="viewcaller_api",
            )

            data = response.json()
            raw_response = data  # Store raw response before processing

            if "data" in data and len(data["data"]) > 0:
                # Format ViewCaller response
                formatted_data = extract_items(
                    data["data"][0], PHONE_LOOKUP_SPECS["viewcaller"]
                )
                return {
                    "found": True,
                    "source": "viewcaller",
                    "data": formatted_data,
                    "confidence": 0.8,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "source": "viewcaller",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": raw_response,
                }
        except Exception as e:
            logger.error(f"ViewCaller search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "error": str(e),
                "_raw_response": raw_response,
            }
