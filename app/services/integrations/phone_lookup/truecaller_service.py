from __future__ import annotations

import logging
from typing import Any

from phone_iso3166.country import phone_country

from app.core.config import settings
from app.core.lookup_extractor import extract_items
from app.core.lookup_specs import PHONE_LOOKUP_SPECS
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class TrueCallerService:
    """Service for TrueCaller API integration"""

    def __init__(self):
        self.name = "TrueCallerService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using TrueCaller API"""
        try:
            logger.info(f"TrueCaller: Searching {country_code}{phone}")

            # TrueCaller API expects ISO 3166-1 alpha-2 country code (e.g., "IN" for India, "US" for USA)
            # Construct full phone number and get ISO country code using phone-iso3166 package
            country_code_clean = (
                country_code.lstrip("+")
                if country_code.startswith("+")
                else country_code
            )
            full_phone = f"+{country_code_clean}{phone}"

            try:
                country_code_iso = phone_country(full_phone)
                if not country_code_iso:
                    # Fallback: if phone_country returns None, try using country_code as-is (might already be ISO)
                    country_code_iso = (
                        country_code_clean
                        if len(country_code_clean) == 2
                        else country_code_clean
                    )
                    logger.warning(
                        f"TrueCaller: phone_country returned None, using '{country_code_iso}' as fallback"
                    )
                logger.info(
                    f"TrueCaller: Using country code '{country_code_iso}' (original: '{country_code}', phone: {full_phone})"
                )
            except Exception as e:
                # Fallback if phone_country fails
                logger.warning(
                    f"TrueCaller: phone_country failed: {e}, using original country code"
                )
                country_code_iso = (
                    country_code_clean
                    if len(country_code_clean) == 2
                    else country_code_clean
                )

            response = await self.client.request(
                "GET",
                "https://truecaller4.p.rapidapi.com/api/v1/getDetails",
                params={"phone": phone, "countryCode": country_code_iso},
                headers={
                    "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                    "X-RapidAPI-Host": "truecaller4.p.rapidapi.com",
                },
                circuit_key="truecaller_api",
            )

            data = response.json()
            raw_response = data  # Store raw response before processing

            # Check for error response (status: False indicates an error)
            if data.get("status") is False or (
                data.get("message") and "error" in data.get("message", "").lower()
            ):
                error_msg = data.get("message", "Unknown error")
                logger.error(f"TrueCaller API error: {error_msg}")
                return {
                    "found": False,
                    "source": "truecaller",
                    "data": None,
                    "confidence": 0.0,
                    "error": error_msg,
                    "_raw_response": raw_response,  # Include raw response for debugging
                }

            if "data" in data and len(data["data"]) > 0:
                # Format TrueCaller response
                formatted_data = extract_items(
                    data["data"][0], PHONE_LOOKUP_SPECS["truecaller"]
                )
                return {
                    "found": True,
                    "source": "truecaller",
                    "data": formatted_data,
                    "confidence": 0.9,
                    "_raw_response": raw_response,  # Include raw response for debugging
                }
            else:
                return {
                    "found": False,
                    "source": "truecaller",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": raw_response,  # Include raw response for debugging
                }
        except Exception as e:
            logger.error(f"TrueCaller search failed: {e}")
            return {"found": False, "error": str(e)}
