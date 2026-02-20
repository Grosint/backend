from __future__ import annotations

import logging
from typing import Any

from app.services.integrations.phone_lookup.aitan import AITANService

logger = logging.getLogger(__name__)


class VehicleLookupOrchestrator:
    """Orchestrator for vehicle lookup external APIs"""

    def __init__(self):
        self.name = "VehicleLookupOrchestrator"

    async def search_vehicle(
        self,
        vehicle_number: str | None,
        chassis_number: str | None = None,
        lookup_type: str = "all",
    ) -> dict[str, Any]:
        """Search vehicle information using available providers.

        Args:
            vehicle_number: Vehicle registration number
            chassis_number: Optional chassis number for chassis-to-RC lookup
            lookup_type: rc, fast-tag, chassis/chasis, or all
        """
        try:
            logger.info(
                "VehicleLookupOrchestrator: Searching vehicle %s", vehicle_number
            )

            normalized_lookup_type = (
                "chassis" if lookup_type == "chasis" else lookup_type
            )

            if normalized_lookup_type == "chassis":
                if not chassis_number:
                    return self._build_error_response(
                        vehicle_number,
                        "chassis_number is required for chassis lookup",
                    )

                if not vehicle_number:
                    async with AITANService() as service:
                        chassis_result = await service._chassis_to_rc(chassis_number)
                        resolved_vehicle_number = (
                            self._extract_vehicle_number_from_chassis_result(
                                chassis_result
                            )
                        )

                        if not resolved_vehicle_number:
                            return self._build_error_response(
                                None,
                                "Vehicle number not found from chassis lookup",
                            )

                        vehicle_number = resolved_vehicle_number
                        result = await service.search_vehicle(
                            vehicle_number, "chassis", chassis_number
                        )
                else:
                    async with AITANService() as service:
                        result = await service.search_vehicle(
                            vehicle_number, "chassis", chassis_number
                        )
            else:
                if not vehicle_number:
                    return self._build_error_response(
                        None,
                        "vehicle_number is required for this lookup type",
                    )

                async with AITANService() as service:
                    result = await service.search_vehicle(
                        vehicle_number, normalized_lookup_type, chassis_number
                    )

            combined_data: dict[str, Any] = {
                "vehicle_number": vehicle_number,
                "lookup_results": {"aitan": result},
                "summary": {
                    "total_sources": 1,
                    "successful_sources": 0,
                    "found_data": False,
                },
            }

            if isinstance(result, dict) and result.get("found", False):
                combined_data["summary"]["successful_sources"] = 1
                combined_data["summary"]["found_data"] = True

            return combined_data

        except Exception as e:
            logger.error(f"VehicleLookupOrchestrator failed: {e}")
            return self._build_error_response(vehicle_number, str(e))

    def _build_error_response(
        self, vehicle_number: str | None, message: str
    ) -> dict[str, Any]:
        return {
            "vehicle_number": vehicle_number,
            "lookup_results": {"aitan": {"error": message}},
            "summary": {
                "total_sources": 1,
                "successful_sources": 0,
                "found_data": False,
            },
        }

    def _extract_vehicle_number_from_chassis_result(
        self, chassis_result: dict[str, Any]
    ) -> str | None:
        if not isinstance(chassis_result, dict):
            return None

        data = chassis_result.get("data")
        if not isinstance(data, dict):
            return None

        vehicle_info = data.get("Vehicle Info")
        if not isinstance(vehicle_info, dict):
            return None

        candidate_keys = {
            "vehicle_no",
            "vehicle_number",
            "registration_no",
            "registration_number",
            "reg_no",
            "rc_number",
            "reg_number",
        }

        for key, value in vehicle_info.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in candidate_keys and isinstance(value, str):
                value = value.strip()
                if value:
                    return value

        return None
