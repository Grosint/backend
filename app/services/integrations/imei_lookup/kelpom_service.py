"""Kelpom IMEI checker service via RapidAPI."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient
from app.utils.string_utils import snake_to_title_case

logger = logging.getLogger(__name__)


class KelpomIMEIService:
    """Service for IMEI lookup via Kelpom IMEI Checker (RapidAPI)."""

    def __init__(self):
        self.name = "KelpomIMEIService"
        self.client = ResilientHttpClient()
        self.base_url = "https://kelpom-imei-checker1.p.rapidapi.com/api"

    async def search_imei(self, imei: str) -> dict[str, Any]:
        """Search IMEI for device model and details."""
        try:
            logger.info(f"Kelpom IMEI: Searching {imei}")

            headers = {
                "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                "X-RapidAPI-Host": "kelpom-imei-checker1.p.rapidapi.com",
            }
            params = {"service": "model", "imei": imei}

            response = await self.client.request(
                "GET",
                self.base_url,
                params=params,
                headers=headers,
                circuit_key="kelpom_imei",
            )

            if response.status_code == 403:
                return {
                    "found": False,
                    "source": "kelpom_imei",
                    "error": "Please try after some time",
                    "confidence": 0.0,
                    "_raw_response": {
                        "status": "error",
                        "message": "Please try after some time",
                    },
                }

            data = response.json()
            raw_response = data

            # API returns either: (a) data.object (legacy) or (b) data.imei + data.model + data.valid
            has_object = (
                data and "object" in data and isinstance(data.get("object"), dict)
            )
            has_model_format = (
                data
                and isinstance(data.get("model"), dict)
                and data.get("valid") is True
            )
            if has_object or has_model_format:
                formatted = self._process_imei_response(data)
                return {
                    "found": True,
                    "source": "kelpom_imei",
                    "data": formatted,
                    "confidence": 0.8,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "source": "kelpom_imei",
                    "data": None,
                    "confidence": 0.0,
                    "error": (
                        data.get("message", "No device data found")
                        if isinstance(data, dict)
                        else "Invalid response"
                    ),
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Kelpom IMEI search failed: {e}")
            return {
                "found": False,
                "source": "kelpom_imei",
                "error": str(e),
                "confidence": 0.0,
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    def _process_imei_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Format IMEI response into key-value list. Handles both object and model formats."""
        if "object" in data and isinstance(data["object"], dict):
            obj = data["object"]
            return [
                {"key": snake_to_title_case(key), "value": value}
                for key, value in obj.items()
            ]
        # model format: imei, model {device, brand, model_nb}, valid
        items: list[dict[str, Any]] = []
        if "imei" in data:
            items.append({"key": "Imei", "value": data["imei"]})
        if "valid" in data:
            items.append({"key": "Valid", "value": data["valid"]})
        model = data.get("model")
        if isinstance(model, dict):
            for key, value in model.items():
                items.append({"key": snake_to_title_case(key), "value": value})
        return items
