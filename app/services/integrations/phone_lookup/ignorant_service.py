from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.resilience import ResilientHttpClient

try:
    from ignorant.modules.shopping.amazon import amazon
    from ignorant.modules.social_media.instagram import instagram
    from ignorant.modules.social_media.snapchat import snapchat

    IGNORANT_MODULES = [amazon, instagram, snapchat]
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import ignorant modules: {e}")
    IGNORANT_MODULES = []

logger = logging.getLogger(__name__)


class IgnorantService:
    """Service for Ignorant package integration - checks if phone is used on various sites"""

    def __init__(self):
        self.name = "IgnorantService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using Ignorant package"""
        try:
            logger.info(f"Ignorant: Searching {country_code}{phone}")

            if not IGNORANT_MODULES:
                raise ImportError(
                    "ignorant package modules not properly installed or imported"
                )

            # Remove '+' from country_code if present
            country_code_clean = (
                country_code.lstrip("+")
                if country_code.startswith("+")
                else country_code
            )

            # Create HTTP client for ignorant
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Use ignorant modules to check phone number across various platforms
                # Note: All modules append to the same results list
                results = []

                # Call all available modules in parallel
                # List append operations are safe in async context
                import asyncio

                tasks = [
                    module(phone, country_code_clean, client, results)
                    for module in IGNORANT_MODULES
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

                full_phone = f"{country_code_clean}{phone}"
                raw_response = {
                    "phone": full_phone,
                    "country_code": country_code_clean,
                    "results": results,
                }

                # Format the response
                if results and len(results) > 0:
                    formatted_data = self._format_response(results)
                    found = any(result.get("exists", False) for result in results)

                    return {
                        "found": found,
                        "source": "ignorant",
                        "data": formatted_data,
                        "confidence": 0.7 if found else 0.0,
                        "_raw_response": raw_response,
                    }
                else:
                    return {
                        "found": False,
                        "source": "ignorant",
                        "data": None,
                        "confidence": 0.0,
                        "_raw_response": raw_response,
                    }
        except Exception as e:
            logger.error(f"Ignorant search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "error": str(e),
                "_raw_response": raw_response,
            }

    def _format_response(self, results: list[dict]) -> list[dict]:
        """Format Ignorant response to standard format"""
        formatted_response = []

        for result in results:
            if not isinstance(result, dict):
                continue

            platform_name = result.get("name", "unknown")
            exists = result.get("exists", False)
            domain = result.get("domain", "")

            if exists:
                # Add platform existence information
                formatted_response.append(
                    {
                        "source": platform_name,
                        "type": "platform_check",
                        "value": f"Phone number found on {platform_name}",
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

                # Add domain if available
                if domain:
                    formatted_response.append(
                        {
                            "source": platform_name,
                            "type": "domain",
                            "value": domain,
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

                # Add method if available
                method = result.get("method", "")
                if method:
                    formatted_response.append(
                        {
                            "source": platform_name,
                            "type": "method",
                            "value": method,
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

        return formatted_response
