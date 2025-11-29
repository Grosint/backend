from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class LeakCheckService:
    """Service for LeakCheck API integration"""

    def __init__(self):
        self.name = "LeakCheckService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using LeakCheck API"""
        try:
            logger.info(f"LeakCheck: Searching {country_code}{phone}")

            # Construct phone queries - try with original and with 91 prefix (for India)
            query_data_list = [phone, f"91{phone}"]

            final_response = []
            all_raw_responses = []

            for index, query in enumerate(query_data_list):
                url = f"https://leakcheck.io/api/v2/query/{query}?type=phone"

                try:
                    response = await self.client.request(
                        "GET",
                        url,
                        headers={
                            "accept": "application/json",
                            "X-API-Key": settings.LEAK_CHECK_API_KEY,
                        },
                        circuit_key="leakcheck_api",
                    )

                    response_json = response.json()
                    all_raw_responses.append(response_json)

                    # Check if API returned success=False
                    if response_json.get("success") is False:
                        logger.warning(
                            f"LeakCheck API returned success=False for query {query}"
                        )
                        continue

                    # Format and add to final response
                    formatted_data = self._format_response(response_json, index)
                    if formatted_data:
                        final_response.extend(formatted_data)

                except Exception as e:
                    logger.warning(
                        f"LeakCheck search failed for query {query}: {e}",
                        exc_info=True,
                    )
                    all_raw_responses.append({"error": str(e), "query": query})
                    continue

            # Combine all raw responses
            raw_response = {
                "queries": query_data_list,
                "responses": all_raw_responses,
            }

            if final_response:
                return {
                    "found": True,
                    "source": "leakcheck",
                    "data": final_response,
                    "confidence": 0.8,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "source": "leakcheck",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"LeakCheck search failed: {e}", exc_info=True)
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "source": "leakcheck",
                "data": None,
                "error": str(e),
                "_raw_response": raw_response,
            }

    def _format_response(
        self, response_json: dict[str, Any], index: int
    ) -> list[dict[str, Any]]:
        """Format LeakCheck response to standard format"""
        formatted_response = []

        # Check if response has result data
        if not response_json.get("success", False):
            return formatted_response

        result = response_json.get("result", [])
        if not result or not isinstance(result, list):
            return formatted_response

        # Process each result item
        for item in result:
            if not isinstance(item, dict):
                continue

            # Extract breach information
            source = item.get("source", "leakcheck")
            email = item.get("email", "")
            username = item.get("username", "")
            domain = item.get("domain", "")
            breach_date = item.get("date", "")

            # Add email if available
            if email:
                formatted_response.append(
                    {
                        "source": source,
                        "type": "email",
                        "value": email,
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            # Add username if available
            if username:
                formatted_response.append(
                    {
                        "source": source,
                        "type": "username",
                        "value": username,
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            # Add domain if available
            if domain:
                formatted_response.append(
                    {
                        "source": source,
                        "type": "domain",
                        "value": domain,
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            # Add breach date if available
            if breach_date:
                formatted_response.append(
                    {
                        "source": source,
                        "type": "breach_date",
                        "value": breach_date,
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

        return formatted_response

    async def search_email(self, email: str) -> dict[str, Any]:
        """Search email address using LeakCheck API"""
        try:
            logger.info(f"LeakCheck: Searching email {email}")

            url = f"https://leakcheck.io/api/v2/query/{email}?type=email"

            try:
                response = await self.client.request(
                    "GET",
                    url,
                    headers={
                        "accept": "application/json",
                        "X-API-Key": settings.LEAK_CHECK_API_KEY,
                    },
                    circuit_key="leakcheck_api",
                )

                response_json = response.json()

                # Check if API returned success=False
                if response_json.get("success") is False:
                    logger.warning(
                        f"LeakCheck API returned success=False for email {email}"
                    )
                    return {
                        "found": False,
                        "source": "leakcheck",
                        "data": None,
                        "confidence": 0.0,
                        "_raw_response": response_json,
                    }

                # Format and return response
                formatted_data = self._format_response(response_json, 0)

                if formatted_data:
                    return {
                        "found": True,
                        "source": "leakcheck",
                        "data": formatted_data,
                        "confidence": 0.8,
                        "_raw_response": response_json,
                    }
                else:
                    return {
                        "found": False,
                        "source": "leakcheck",
                        "data": None,
                        "confidence": 0.0,
                        "_raw_response": response_json,
                    }

            except Exception as e:
                logger.warning(
                    f"LeakCheck email search failed: {e}",
                    exc_info=True,
                )
                raw_response = {"error": str(e), "email": email}
                return {
                    "found": False,
                    "source": "leakcheck",
                    "data": None,
                    "confidence": 0.0,
                    "error": str(e),
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"LeakCheck email search failed: {e}", exc_info=True)
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "source": "leakcheck",
                "data": None,
                "error": str(e),
                "_raw_response": raw_response,
            }
