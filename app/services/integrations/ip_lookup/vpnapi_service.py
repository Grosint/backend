"""VPNAPI.io IP lookup service."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient
from app.utils.string_utils import snake_to_title_case

logger = logging.getLogger(__name__)


class VPNAPIService:
    """Service for VPNAPI.io IP geolocation and security lookup."""

    def __init__(self):
        self.name = "VPNAPIService"
        self.client = ResilientHttpClient()
        self.base_url = "https://vpnapi.io/api"

    async def search_ip(self, ip: str) -> dict[str, Any]:
        """Search IP address for geolocation, network, and security info."""
        try:
            logger.info(f"VPNAPI: Searching IP {ip}")

            url = f"{self.base_url}/{ip}"
            params = (
                {"key": settings.VPNAPI_IO_API_KEY}
                if settings.VPNAPI_IO_API_KEY
                else {}
            )
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
            }

            response = await self.client.request(
                "GET",
                url,
                params=params,
                headers=headers,
                circuit_key="vpnapi_io",
            )

            data = response.json()
            raw_response = data

            if data and "error" not in data:
                formatted = self._process_ip_response(data)
                return {
                    "found": True,
                    "source": "vpnapi",
                    "data": formatted,
                    "confidence": 0.8,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "source": "vpnapi",
                    "data": None,
                    "confidence": 0.0,
                    "error": data.get("message", "No data found"),
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"VPNAPI IP search failed: {e}")
            return {
                "found": False,
                "source": "vpnapi",
                "error": str(e),
                "confidence": 0.0,
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    def _process_ip_response(self, res: dict[str, Any]) -> dict[str, Any]:
        """Process VPNAPI response into structured format."""
        result: dict[str, Any] = {}
        map_url = None

        if res and "location" in res:
            location = res["location"]
            latitude = location.get("latitude")
            longitude = location.get("longitude")

            if latitude is not None and longitude is not None:
                map_url = f"https://www.google.com/maps?q={latitude},{longitude}&z=20"

            rest_location = {
                k: v for k, v in location.items() if k not in {"latitude", "longitude"}
            }
            filtered_location = {
                key: value
                for key, value in rest_location.items()
                if value is not None and value != ""
            }

            result["location"] = [
                {"key": snake_to_title_case(key), "value": value}
                for key, value in filtered_location.items()
            ]
            if map_url:
                result["location"].append({"key": "Map", "value": map_url})

        if "network" in res:
            result["network"] = [
                {
                    "key": (
                        "ORG"
                        if key == "autonomous_system_organization"
                        else snake_to_title_case(key)
                    ),
                    "value": value,
                }
                for key, value in res["network"].items()
            ]

        if "security" in res:
            result["security"] = [
                {"key": snake_to_title_case(key), "value": value}
                for key, value in res["security"].items()
            ]

        return result
