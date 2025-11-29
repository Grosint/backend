from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class HLRService:
    """Service for HLR (Home Location Register) API integration"""

    def __init__(self):
        self.name = "HLRService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using HLR API"""
        try:
            logger.info(f"HLR: Searching {country_code}{phone}")

            # Construct full phone number
            phone_number = country_code + phone

            # Prepare request
            headers = {
                "X-Basic": settings.HLR_API_KEY,
            }
            json_data = {"msisdn": str(phone_number), "route": None, "storage": None}

            response = await self.client.request(
                "POST",
                "https://www.hlr-lookups.com/api/v2/hlr-lookup",
                json=json_data,
                headers=headers,
                circuit_key="hlr_api",
            )

            data = response.json()
            raw_response = data  # Store raw response before processing

            # Format HLR response
            formatted_data = self._format_response(data)

            # Determine if data was found (HLR typically returns status information)
            found = self._is_data_found(data)

            return {
                "found": found,
                "source": "hlr",
                "data": formatted_data,
                "confidence": 0.8 if found else 0.0,
                "_raw_response": raw_response,
            }
        except Exception as e:
            logger.error(f"HLR search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "source": "hlr",
                "error": str(e),
                "_raw_response": raw_response,
            }

    def _is_data_found(self, data: dict[str, Any]) -> bool:
        """Determine if HLR response contains valid data"""
        # Check for common HLR response indicators
        if not isinstance(data, dict):
            return False

        # Check for status fields that indicate valid response
        status = data.get("status")
        if status and isinstance(status, str):
            # Valid statuses typically include "active", "valid", etc.
            status_lower = status.lower()
            if status_lower in ["active", "valid", "reachable"]:
                return True
            if status_lower in ["invalid", "unknown", "error"]:
                return False

        # Check for presence of carrier or network information
        if data.get("carrier") or data.get("network") or data.get("operator"):
            return True

        # Check for country information
        if data.get("country") or data.get("country_code"):
            return True

        # If we have any meaningful data, consider it found
        return len(data) > 0 and not data.get("error")

    def _format_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Format HLR response to standard format"""
        formatted_response = []

        if not isinstance(data, dict):
            return formatted_response

        # Extract carrier/network information
        carrier = data.get("carrier") or data.get("network") or data.get("operator")
        if carrier:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "carrier",
                    "value": str(carrier),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Extract country information
        country = data.get("country") or data.get("country_name")
        if country:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "country",
                    "value": str(country),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Extract country code
        country_code = data.get("country_code") or data.get("countryCode")
        if country_code:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "country_code",
                    "value": str(country_code),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Extract status
        status = data.get("status")
        if status:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "status",
                    "value": str(status),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Extract number type (mobile, landline, etc.)
        number_type = (
            data.get("number_type") or data.get("numberType") or data.get("type")
        )
        if number_type:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "number_type",
                    "value": str(number_type),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Extract ported information if available
        ported = data.get("ported") or data.get("is_ported")
        if ported is not None:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "ported",
                    "value": "Yes" if ported else "No",
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Extract roaming information if available
        roaming = data.get("roaming") or data.get("is_roaming")
        if roaming is not None:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "roaming",
                    "value": "Yes" if roaming else "No",
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Extract any additional fields that might be present
        # Common HLR fields
        for field in ["mcc", "mnc", "imsi", "msisdn"]:
            if data.get(field):
                formatted_response.append(
                    {
                        "source": "hlr",
                        "type": field.lower(),
                        "value": str(data[field]),
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        return formatted_response
