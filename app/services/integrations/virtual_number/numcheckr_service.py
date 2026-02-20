"""NumCheckr virtual number verification service."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class NumCheckrService:
    """Service for virtual/throwaway number verification via NumCheckr API."""

    def __init__(self):
        self.name = "NumCheckrService"
        self.client = ResilientHttpClient()
        self.base_url = "https://numcheckr.com/api/check-number"

    def _to_e164(self, phone_number: str, country_code: str = "+91") -> str:
        """Normalize phone to E.164. NumCheckr requires + and country code."""
        if not phone_number:
            return phone_number
        if phone_number.startswith("+"):
            return phone_number
        cc = country_code.strip()
        if not cc.startswith("+"):
            cc = "+" + cc
        digits = "".join(c for c in phone_number if c.isdigit())
        return cc + digits

    async def check_number(
        self, phone_number: str, country_code: str = "+91"
    ) -> dict[str, Any]:
        """Check if phone number is virtual/throwaway. NumCheckr requires E.164 format."""
        try:
            e164 = self._to_e164(phone_number, country_code)
            logger.info(f"NumCheckr: Checking {e164}")

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.NUMCHECKR_API_KEY}",
            }
            payload = {"phone": e164}

            response = await self.client.request(
                "POST",
                self.base_url,
                json=payload,
                headers=headers,
                circuit_key="numcheckr",
            )

            data = response.json()
            raw_response = data

            if data and "error" not in data:
                return {
                    "found": True,
                    "source": "numcheckr",
                    "data": data,
                    "confidence": 0.8,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "source": "numcheckr",
                    "data": data,
                    "confidence": 0.0,
                    "error": (
                        data.get("message", "No data")
                        if isinstance(data, dict)
                        else "Invalid response"
                    ),
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"NumCheckr check failed: {e}")
            return {
                "found": False,
                "source": "numcheckr",
                "error": str(e),
                "confidence": 0.0,
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }
