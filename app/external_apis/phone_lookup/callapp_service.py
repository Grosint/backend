from __future__ import annotations

import logging
from typing import Any

from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class CallAppService:
    """Service for CallApp API integration"""

    def __init__(self):
        self.name = "CallAppService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using CallApp API"""
        try:
            logger.info(f"CallApp: Searching {country_code}{phone}")

            # Remove '+' from country_code if present, then construct phone number with + prefix
            country_code_clean = (
                country_code.lstrip("+")
                if country_code.startswith("+")
                else country_code
            )
            phone_number = "+" + country_code_clean + phone

            # CallApp API configuration - hardcoded values
            call_app_get = "https://s.callapp.com/callapp-server/csrch"
            call_app_myp = "fb.216563187929545"
            call_app_tk = "0039875511"
            call_app_cvc = "2086"

            # Prepare params as per CallApp API requirements
            params = {
                "cpn": phone_number,
                "myp": call_app_myp,
                "ibs": 0,
                "cid": 0,
                "tk": call_app_tk,
                "cvc": call_app_cvc,
            }

            response = await self.client.request(
                "GET",
                call_app_get,
                params=params,
                circuit_key="callapp_api",
                allowed_statuses=[525],  # Allow 525 status code
            )

            # Handle status code 525 (special case)
            if response.status_code == 525:
                raw_response = {"status_code": 525, "message": "Service unavailable"}
                formatted_data = self._format_response(None)
                return {
                    "found": False,
                    "source": "callapp",
                    "data": formatted_data,
                    "confidence": 0.0,
                    "_raw_response": raw_response,
                }

            # Parse JSON response
            try:
                data = response.json()
                raw_response = data  # Store raw response before processing
            except ValueError:
                # Invalid JSON response
                raw_response = {
                    "error": "Invalid JSON response",
                    "status_code": response.status_code,
                }
                formatted_data = self._format_response(None)
                return {
                    "found": False,
                    "source": "callapp",
                    "data": formatted_data,
                    "confidence": 0.0,
                    "_raw_response": raw_response,
                }

            # Format response
            formatted_data = self._format_response(data)
            found = formatted_data[0]["value"] is not None if formatted_data else False

            return {
                "found": found,
                "source": "callapp",
                "data": formatted_data,
                "confidence": 0.8 if found else 0.0,
                "_raw_response": raw_response,
            }
        except Exception as e:
            logger.error(f"CallApp search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            formatted_data = self._format_response(None)
            return {
                "found": False,
                "source": "callapp",
                "data": formatted_data,
                "error": str(e),
                "_raw_response": raw_response,
            }

    def _format_response(self, data: dict | None) -> list[dict]:
        """Format CallApp response to standard format"""
        formatted_response = []

        if data and "name" in data and data["name"]:
            formatted_response.append(
                {
                    "source": "callapp",
                    "type": "name",
                    "value": data["name"],
                    "showSource": False,
                    "category": "TEXT",
                }
            )
        else:
            formatted_response.append(
                {
                    "source": "callapp",
                    "type": "name",
                    "value": None,
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        return formatted_response
