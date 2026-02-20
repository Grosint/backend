"""
AITAN Service Module

This module provides AITAN Labs API integration with separate modules for
phone, vehicle, and bank lookups.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.resilience import ResilientHttpClient
from app.services.integrations.phone_lookup.aitan import bank, phone, vehicle
from app.services.integrations.phone_lookup.aitan.vehicle import (
    INSURANCE_INFO_AITAN,
    OWNER_INFO_AITAN,
    VEHICLE_INFO_AITAN,
)

logger = logging.getLogger(__name__)

# Explicitly declare public exports
__all__ = [
    "AITANService",
    "INSURANCE_INFO_AITAN",
    "OWNER_INFO_AITAN",
    "VEHICLE_INFO_AITAN",
]


class AITANService:
    """Service for AITAN Labs API integration with configuration-based routing"""

    # Configuration mapping lookup types to functions
    LOOKUP_CONFIG = {
        "phone-lookup": [
            "mobile_to_profile",
            # "mobile_prefill",
            "mobile_address",
            "mobile_to_vpa_advance",
        ],
        "vehicle-lookup": [
            "rc_advance",
            "challan_advance",
            "chassis_to_rc",
            "mobile_to_fasttag_history",
        ],
        "rc": ["rc_advance"],
        "fast-tag": ["mobile_to_fasttag_history"],
        "chassis": ["chassis_to_rc", "rc_advance"],
        "all": ["rc_advance", "chassis_to_rc", "mobile_to_fasttag_history"],
        "bank-lookup": [
            "mobile_to_vpa_advance",
            "vpa_360",
            "bank_verification_penniless",
        ],
    }

    def __init__(self):
        self.name = "AITANService"
        self.client = ResilientHttpClient()
        self.base_url = "https://api.aitanlabs.net"
        self.base_url_com = "https://api.aitanlabs.com"

        # Initialize phone, vehicle, and bank modules
        self._phone_service = phone.AITANPhoneService(self)
        self._vehicle_service = vehicle.AITANVehicleService(self)
        self._bank_service = bank.AITANBankService(self)

    async def aclose(self) -> None:
        """
        Close underlying HTTP resources.

        This ensures the wrapped httpx.AsyncClient (via ResilientHttpClient)
        is properly closed and its connection pools are released.
        """
        await self.client.aclose()

    async def __aenter__(self) -> AITANService:
        """
        Support usage as an async context manager:

            async with AITANService() as service:
                ...
        """
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def search_phone(
        self, country_code: str, phone: str, lookup_type: str = "phone-lookup"
    ) -> dict[str, Any]:
        """Search phone number using AITAN API"""
        return await self._phone_service.search_phone(country_code, phone, lookup_type)

    async def search_vehicle(
        self,
        vehicle_number: str,
        lookup_type: str = "vehicle-lookup",
        chassis_number: str | None = None,
    ) -> dict[str, Any]:
        """Search vehicle using AITAN API"""
        return await self._vehicle_service.search_vehicle(
            vehicle_number, lookup_type, chassis_number
        )

    # Expose phone methods
    async def _mobile_to_profile(self, phone_number: str) -> dict[str, Any]:
        return await self._phone_service._mobile_to_profile(phone_number)

    async def _mobile_prefill(self, phone_number: str) -> dict[str, Any]:
        return await self._phone_service._mobile_prefill(phone_number)

    async def _mobile_address(self, phone_number: str) -> dict[str, Any]:
        return await self._phone_service._mobile_address(phone_number)

    async def _mobile_to_vpa_advance(self, phone_number: str) -> dict[str, Any]:
        return await self._phone_service._mobile_to_vpa_advance(phone_number)

    # Expose vehicle methods
    async def _rc_advance(self, vehicle_number: str) -> dict[str, Any]:
        return await self._vehicle_service._rc_advance(vehicle_number)

    async def _challan_advance(self, vehicle_number: str) -> dict[str, Any]:
        return await self._vehicle_service._challan_advance(vehicle_number)

    async def _chassis_to_rc(self, chassis_number: str) -> dict[str, Any]:
        return await self._vehicle_service._chassis_to_rc(chassis_number)

    async def _mobile_to_fasttag_history(self, vehicle_number: str) -> dict[str, Any]:
        return await self._vehicle_service._mobile_to_fasttag_history(vehicle_number)
