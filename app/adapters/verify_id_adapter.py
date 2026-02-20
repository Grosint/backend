"""Verify ID adapter (PAN, DL, Voter ID) using Befisc."""

from __future__ import annotations

import logging
from typing import Any, Literal

from app.adapters.base import OSINTAdapter
from app.services.integrations.phone_lookup.befisc_service import BefiscService

logger = logging.getLogger(__name__)

IdType = Literal["pan", "dl", "voter", "passport"]


class VerifyIdAdapter(OSINTAdapter):
    """Adapter for ID verification (PAN, DL, Voter ID) via Befisc."""

    def __init__(self):
        super().__init__()
        self.name = "VerifyIdAdapter"
        self.befisc = BefiscService()

    async def search_verify_id(
        self,
        id_type: IdType,
        value: str,
        dob: str | None = None,
    ) -> dict[str, Any]:
        """Search/verify ID by type. For DL, dob (DD-MM-YYYY) is required."""
        try:
            logger.info(f"VerifyIdAdapter: Verifying {id_type}")

            if id_type == "pan":
                result = await self.befisc._pan_search(value)
            elif id_type == "dl":
                if not dob:
                    result = {
                        "found": False,
                        "source": "befisc",
                        "error": "dob (DD-MM-YYYY) is required for driving license",
                        "confidence": 0.0,
                    }
                else:
                    result = await self.befisc._driving_license_search(value, dob)
            elif id_type == "voter":
                result = await self.befisc._voter_id_search(value)
            elif id_type == "passport":
                result = {
                    "found": False,
                    "source": "befisc",
                    "error": "Passport verification not yet implemented",
                    "confidence": 0.0,
                }
            else:
                result = {
                    "found": False,
                    "source": "befisc",
                    "error": f"Unknown id_type: {id_type}",
                    "confidence": 0.0,
                }

            combined = self._to_lookup_format(result, "befisc")
            return self.normalize_success_response(combined)

        except Exception as e:
            logger.error(f"VerifyIdAdapter search failed: {e}")
            return self.normalize_error_response(e)

    def _to_lookup_format(self, result: dict[str, Any], source: str) -> dict[str, Any]:
        """Convert service result to lookup_results format."""
        return {
            "lookup_results": {source: result},
            "summary": {
                "total_sources": 1,
                "successful_sources": 1 if result.get("found", False) else 0,
                "found_data": result.get("found", False),
            },
        }
