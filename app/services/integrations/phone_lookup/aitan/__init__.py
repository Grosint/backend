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

logger = logging.getLogger(__name__)

# Constants for vehicle RC processing
VEHICLE_INFO_AITAN = [
    "vehicle_no",
    "registration_no",
    "chassis_no",
    "engine_no",
    "vehicle_class",
    "fuel_type",
    "maker_model",
    "manufacturing_date",
    "registration_date",
    "fitness_upto",
    "tax_upto",
    "insurance_upto",
    "permit_upto",
    "permit_type",
    "financer",
    "owner_name",
    "owner_father_name",
    "owner_address",
    "rc_status",
    "vehicle_color",
    "norms",
    "vehicle_category",
]

OWNER_INFO_AITAN = [
    "owner_name",
    "owner_father_name",
    "owner_address",
    "split_permanent_address",
    "split_present_address",
    "owner_mobile",
    "owner_email",
]

INSURANCE_INFO_AITAN = [
    "insurance_company",
    "insurance_policy_no",
    "insurance_valid_from",
    "insurance_valid_to",
    "insurance_upto",
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
