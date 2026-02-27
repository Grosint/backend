"""Adapter for Dark Web Leaked Data Search via LeakCheck API."""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.services.integrations.phone_lookup.leakcheck_service import LeakCheckService

logger = logging.getLogger(__name__)


class DarkWebLeakAdapter(OSINTAdapter):
    """Adapter for dark web leaked data search (email, mobile, username, keyword)."""

    def __init__(self):
        super().__init__()
        self.name = "DarkWebLeakAdapter"
        self._leak_service = LeakCheckService()

    async def search_leak(
        self,
        query_type: str,
        query_data: str,
        country_code: str = "+91",
    ) -> dict[str, Any]:
        """
        Search leaked data by type: email, mobile, username, keyword.

        Args:
            query_type: One of email, mobile, username, keyword
            query_data: Search value (email, phone, username, or keyword)
            country_code: Country code for mobile (e.g. +91). Used when query_type is mobile.

        Returns:
            dict: {success, data: {lookup_results: {leakcheck: {...}}, summary: {...}}}
        """
        try:
            logger.info(
                "DarkWebLeakAdapter: Searching %s=%s (cc=%s)",
                query_type,
                query_data[:20] + "..." if len(query_data) > 20 else query_data,
                country_code,
            )
            result = await self._leak_service.search_leak(
                query_type=query_type,
                query_data=query_data,
                country_code=country_code,
            )
            found = result.get("found", False)
            return {
                "success": True,
                "data": {
                    "lookup_results": {"leakcheck": result},
                    "summary": {
                        "total_sources": 1,
                        "successful_sources": 1 if found else 0,
                        "found_data": found,
                    },
                },
            }
        except Exception as e:
            logger.error("DarkWebLeakAdapter search failed: %s", e)
            return {
                "success": False,
                "data": {
                    "lookup_results": {
                        "leakcheck": {
                            "found": False,
                            "source": "leakcheck",
                            "data": None,
                            "error": str(e),
                            "confidence": 0.0,
                        }
                    },
                    "summary": {
                        "total_sources": 1,
                        "successful_sources": 0,
                        "found_data": False,
                    },
                },
            }
