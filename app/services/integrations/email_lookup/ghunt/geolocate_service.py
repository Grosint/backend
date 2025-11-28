from __future__ import annotations

import logging
from typing import Any

import httpx
from ghunt.apis.geolocation import GeolocationHttp

from app.services.integrations.email_lookup.ghunt.credentials_manager import (
    GHuntCredentialsManager,
)

logger = logging.getLogger(__name__)


class GHuntGeolocateService:
    """Service for GHunt Geolocation API integration"""

    def __init__(self):
        self.name = "GHuntGeolocateService"
        self._creds = None
        self._geo_api = None

    def _get_credentials(self):
        """Get GHunt credentials"""
        if self._creds is None:
            self._creds = GHuntCredentialsManager.get_credentials()
        return self._creds

    def _get_geo_api(self):
        """Get Geolocation API instance"""
        if self._geo_api is None:
            creds = self._get_credentials()
            self._geo_api = GeolocationHttp(creds)
        return self._geo_api

    async def geolocate_bssid(self, bssid: str) -> dict[str, Any]:
        """Geolocate a WiFi BSSID (MAC address)"""
        try:
            geo_api = self._get_geo_api()

            async with httpx.AsyncClient() as client:
                result = await geo_api.geolocate(client, bssid)

                if not result:
                    return {"found": False, "error": "BSSID not found"}

                return {
                    "found": True,
                    "bssid": bssid,
                    "location": {
                        "latitude": result.get("location", {}).get("lat"),
                        "longitude": result.get("location", {}).get("lng"),
                        "accuracy": result.get("accuracy"),
                    },
                }
        except Exception as e:
            logger.error(f"GHunt Geolocation API error: {e}")
            return {"found": False, "error": str(e)}
