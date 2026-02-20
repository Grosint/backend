from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.orchestrators.vehicle_lookup_orchestrator import (
    VehicleLookupOrchestrator,
)

logger = logging.getLogger(__name__)


class VehicleLookupAdapter(OSINTAdapter):
    """Adapter for vehicle lookup APIs"""

    def __init__(self):
        super().__init__()
        self.name = "VehicleLookupAdapter"
        self.orchestrator = VehicleLookupOrchestrator()

    async def search_vehicle(
        self,
        vehicle_number: str | None,
        chassis_number: str | None = None,
        lookup_type: str = "all",
    ) -> dict[str, Any]:
        """Search vehicle data using the vehicle lookup orchestrator."""
        try:
            logger.info(f"VehicleLookupAdapter: Searching {vehicle_number}")

            result = await self.orchestrator.search_vehicle(
                vehicle_number,
                chassis_number=chassis_number,
                lookup_type=lookup_type,
            )

            return self.normalize_success_response(result)

        except Exception as e:
            logger.error(f"VehicleLookupAdapter search failed: {e}")
            return self.normalize_error_response(e)
