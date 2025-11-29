from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class EyeconService:
    """Service for Eyecon API integration"""

    def __init__(self):
        self.name = "EyeconService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using Eyecon API"""
        try:
            logger.info(f"Eyecon: Searching {country_code}{phone}")

            response = await self.client.request(
                "GET",
                "https://eyecon.p.rapidapi.com/api/v1/search",
                params={"code": country_code, "number": phone},
                headers={
                    "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                    "X-RapidAPI-Host": "eyecon.p.rapidapi.com",
                },
                circuit_key="eyecon_api",
            )

            data = response.json()
            raw_response = data  # Store raw response before processing

            if "data" in data:
                # Format Eyecon response
                formatted_data = self._format_response(data["data"])
                return {
                    "found": True,
                    "source": "eyecon",
                    "data": formatted_data,
                    "confidence": 0.7,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "source": "eyecon",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": raw_response,
                }
        except Exception as e:
            logger.error(f"Eyecon search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "error": str(e),
                "_raw_response": raw_response,
            }

    def _format_response(self, data: dict) -> list[dict]:
        """Format Eyecon response to standard format"""
        formatted_response = []

        # Extract full name
        if "fullName" in data:
            formatted_response.append(
                {
                    "source": "eyecon",
                    "type": "name",
                    "value": data["fullName"],
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Extract image
        if "image" in data:
            formatted_response.append(
                {
                    "source": "eyecon",
                    "type": "image",
                    "value": data["image"],
                    "showSource": False,
                    "category": "IMAGE",
                }
            )

        # Extract other names
        if "otherNames" in data and len(data["otherNames"]) != 0:
            for item in data["otherNames"]:
                formatted_response.append(
                    {
                        "source": "eyecon",
                        "type": "name",
                        "value": item["name"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        # Extract Facebook info
        if "facebookID" in data and "url" in data["facebookID"]:
            formatted_response.append(
                {
                    "source": "Account Exist",
                    "type": "facebook",
                    "value": "Yes",
                    "showSource": True,
                    "category": "TEXT",
                }
            )
            formatted_response.append(
                {
                    "source": "eyecon",
                    "type": "facebook",
                    "value": data["facebookID"]["url"],
                    "showSource": False,
                    "category": "LINK",
                }
            )
            formatted_response.append(
                {
                    "source": "eyecon",
                    "type": "image",
                    "value": data["facebookID"]["profileURL"],
                    "showSource": False,
                    "category": "IMAGE",
                }
            )
        else:
            formatted_response.append(
                {
                    "source": "Account Exist",
                    "type": "facebook",
                    "value": "No",
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        return formatted_response
