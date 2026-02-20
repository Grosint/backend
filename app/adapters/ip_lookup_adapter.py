"""IP lookup adapter using VPNAPI.io."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.integrations.ip_lookup.vpnapi_service import VPNAPIService

logger = logging.getLogger(__name__)


class IPLookupAdapter(OSINTAdapter):
    """Adapter for IP geolocation and security lookup via VPNAPI.io."""

    def __init__(self):
        super().__init__()
        self.name = "IPLookupAdapter"
        self.service = VPNAPIService()

    async def search_ip(self, ip: str) -> dict[str, Any]:
        """Search IP address."""
        try:
            logger.info(f"IPLookupAdapter: Searching {ip}")

            result = await self.service.search_ip(ip)

            combined = {
                "lookup_results": {"vpnapi": result},
                "summary": {
                    "total_sources": 1,
                    "successful_sources": 1 if result.get("found", False) else 0,
                    "found_data": result.get("found", False),
                },
            }
            return self.normalize_success_response(combined)

        except Exception as e:
            logger.error(f"IPLookupAdapter search failed: {e}")
            return self.normalize_error_response(e)
