from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class HLRService:
    """Service for HLR (Home Location Register) API integration"""

    def __init__(self):
        self.name = "HLRService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using HLR API"""
        try:
            logger.info(f"HLR: Searching {country_code}{phone}")

            # Construct full phone number
            phone_number = country_code + phone

            # Prepare request
            headers = {
                "X-Basic": settings.HLR_API_KEY,
            }
            json_data = {"msisdn": str(phone_number), "route": None, "storage": None}

            response = await self.client.request(
                "POST",
                "https://www.hlr-lookups.com/api/v2/hlr-lookup",
                json=json_data,
                headers=headers,
                circuit_key="hlr_api",
            )

            data = response.json()
            raw_response = data  # Store raw response before processing

            # Format HLR response
            formatted_data = self._format_response(data)

            # Determine if data was found (HLR typically returns status information)
            found = self._is_data_found(data)

            return {
                "found": found,
                "source": "hlr",
                "data": formatted_data,
                "confidence": 0.8 if found else 0.0,
                "_raw_response": raw_response,
            }
        except Exception as e:
            logger.error(f"HLR search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "source": "hlr",
                "error": str(e),
                "_raw_response": raw_response,
            }

    def _is_data_found(self, data: dict[str, Any]) -> bool:
        """Determine if HLR response contains valid data"""
        # Check for common HLR response indicators
        if not isinstance(data, dict):
            return False

        # Check for connectivity status
        connectivity_status = data.get("connectivity_status")
        if connectivity_status:
            status_lower = str(connectivity_status).lower()
            if status_lower in ["connected", "active", "valid", "reachable"]:
                return True
            if status_lower in ["disconnected", "invalid", "unknown", "error"]:
                return False

        # Check for processing status
        processing_status = data.get("processing_status")
        if processing_status:
            status_lower = str(processing_status).lower()
            if status_lower in ["completed", "success"]:
                return True
            if status_lower in ["failed", "error"]:
                return False

        # Check for status fields that indicate valid response (legacy)
        status = data.get("status")
        if status and isinstance(status, str):
            # Valid statuses typically include "active", "valid", etc.
            status_lower = status.lower()
            if status_lower in ["active", "valid", "reachable"]:
                return True
            if status_lower in ["invalid", "unknown", "error"]:
                return False

        # Check for presence of network information
        if (
            data.get("original_network_name")
            or data.get("ported_network_name")
            or data.get("carrier")
            or data.get("network")
            or data.get("operator")
        ):
            return True

        # Check for country information
        if (
            data.get("original_country_name")
            or data.get("original_country_code")
            or data.get("country")
            or data.get("country_code")
        ):
            return True

        # Check for MSISDN or network codes
        if data.get("msisdn") or data.get("mcc") or data.get("mnc"):
            return True

        # If we have any meaningful data and no error, consider it found
        return len(data) > 0 and not data.get("error")

    def _format_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Format HLR response to standard format"""
        formatted_response = []

        if not isinstance(data, dict):
            return formatted_response

        # Extract MSISDN (phone number)
        msisdn = data.get("msisdn")
        if msisdn:
            formatted_response.append(
                {
                    "source": "Phone Number",
                    "type": "msisdn",
                    "value": str(msisdn),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract connectivity status
        connectivity_status = data.get("connectivity_status")
        if connectivity_status:
            formatted_response.append(
                {
                    "source": "Connectivity Status",
                    "type": "status",
                    "value": str(connectivity_status),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract processing status
        processing_status = data.get("processing_status")
        if processing_status:
            formatted_response.append(
                {
                    "source": "Processing Status",
                    "type": "status",
                    "value": str(processing_status),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract original network information
        original_network_name = data.get("original_network_name")
        if original_network_name:
            formatted_response.append(
                {
                    "source": "Original Network",
                    "type": "network",
                    "value": str(original_network_name),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        original_country_name = data.get("original_country_name")
        if original_country_name:
            formatted_response.append(
                {
                    "source": "Original Country",
                    "type": "country",
                    "value": str(original_country_name),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        original_country_code = data.get("original_country_code")
        if original_country_code:
            formatted_response.append(
                {
                    "source": "Original Country Code",
                    "type": "country_code",
                    "value": str(original_country_code),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        original_country_prefix = data.get("original_country_prefix")
        if original_country_prefix:
            formatted_response.append(
                {
                    "source": "Original Country Prefix",
                    "type": "country_prefix",
                    "value": str(original_country_prefix),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract ported information
        is_ported = data.get("is_ported")
        if is_ported is not None:
            formatted_response.append(
                {
                    "source": "Is Ported",
                    "type": "ported",
                    "value": "Yes" if is_ported else "No",
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        if is_ported:
            ported_network_name = data.get("ported_network_name")
            if ported_network_name:
                formatted_response.append(
                    {
                        "source": "Ported Network",
                        "type": "network",
                        "value": str(ported_network_name),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            ported_country_name = data.get("ported_country_name")
            if ported_country_name:
                formatted_response.append(
                    {
                        "source": "Ported Country",
                        "type": "country",
                        "value": str(ported_country_name),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            ported_country_code = data.get("ported_country_code")
            if ported_country_code:
                formatted_response.append(
                    {
                        "source": "Ported Country Code",
                        "type": "country_code",
                        "value": str(ported_country_code),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            ported_country_prefix = data.get("ported_country_prefix")
            if ported_country_prefix:
                formatted_response.append(
                    {
                        "source": "Ported Country Prefix",
                        "type": "country_prefix",
                        "value": str(ported_country_prefix),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

        # Extract roaming information
        is_roaming = data.get("is_roaming")
        if is_roaming is not None:
            formatted_response.append(
                {
                    "source": "Is Roaming",
                    "type": "roaming",
                    "value": "Yes" if is_roaming else "No",
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        if is_roaming:
            roaming_network_name = data.get("roaming_network_name")
            if roaming_network_name:
                formatted_response.append(
                    {
                        "source": "Roaming Network",
                        "type": "network",
                        "value": str(roaming_network_name),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            roaming_country_name = data.get("roaming_country_name")
            if roaming_country_name:
                formatted_response.append(
                    {
                        "source": "Roaming Country",
                        "type": "country",
                        "value": str(roaming_country_name),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            roaming_country_code = data.get("roaming_country_code")
            if roaming_country_code:
                formatted_response.append(
                    {
                        "source": "Roaming Country Code",
                        "type": "country_code",
                        "value": str(roaming_country_code),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            roaming_country_prefix = data.get("roaming_country_prefix")
            if roaming_country_prefix:
                formatted_response.append(
                    {
                        "source": "Roaming Country Prefix",
                        "type": "country_prefix",
                        "value": str(roaming_country_prefix),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

        # Extract network codes
        mccmnc = data.get("mccmnc")
        if mccmnc:
            formatted_response.append(
                {
                    "source": "MCCMNC",
                    "type": "network_code",
                    "value": str(mccmnc),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        mcc = data.get("mcc")
        if mcc:
            formatted_response.append(
                {
                    "source": "MCC",
                    "type": "network_code",
                    "value": str(mcc),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        mnc = data.get("mnc")
        if mnc:
            formatted_response.append(
                {
                    "source": "MNC",
                    "type": "network_code",
                    "value": str(mnc),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        imsi = data.get("imsi")
        if imsi:
            formatted_response.append(
                {
                    "source": "IMSI",
                    "type": "network_code",
                    "value": str(imsi),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        msin = data.get("msin")
        if msin:
            formatted_response.append(
                {
                    "source": "MSIN",
                    "type": "network_code",
                    "value": str(msin),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        msc = data.get("msc")
        if msc:
            formatted_response.append(
                {
                    "source": "MSC",
                    "type": "network_code",
                    "value": str(msc),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract cost information
        cost = data.get("cost")
        if cost:
            formatted_response.append(
                {
                    "source": "Cost",
                    "type": "cost",
                    "value": str(cost),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract timestamp
        timestamp = data.get("timestamp")
        if timestamp:
            formatted_response.append(
                {
                    "source": "Timestamp",
                    "type": "timestamp",
                    "value": str(timestamp),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract data source
        data_source = data.get("data_source")
        if data_source:
            formatted_response.append(
                {
                    "source": "Data Source",
                    "type": "data_source",
                    "value": str(data_source),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract route
        route = data.get("route")
        if route:
            formatted_response.append(
                {
                    "source": "Route",
                    "type": "route",
                    "value": str(route),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract routing instruction
        routing_instruction = data.get("routing_instruction")
        if routing_instruction:
            formatted_response.append(
                {
                    "source": "Routing Instruction",
                    "type": "routing",
                    "value": str(routing_instruction),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract storage
        storage = data.get("storage")
        if storage:
            formatted_response.append(
                {
                    "source": "Storage",
                    "type": "storage",
                    "value": str(storage),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract error information if present
        error_code = data.get("error_code")
        if error_code:
            formatted_response.append(
                {
                    "source": "Error Code",
                    "type": "error",
                    "value": str(error_code),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        error_description = data.get("error_description")
        if error_description:
            formatted_response.append(
                {
                    "source": "Error Description",
                    "type": "error",
                    "value": str(error_description),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract ID if present
        lookup_id = data.get("id")
        if lookup_id:
            formatted_response.append(
                {
                    "source": "Lookup ID",
                    "type": "id",
                    "value": str(lookup_id),
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Fallback: Extract legacy fields if they exist (for backward compatibility)
        carrier = data.get("carrier") or data.get("network") or data.get("operator")
        if carrier and not original_network_name:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "carrier",
                    "value": str(carrier),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        country = data.get("country") or data.get("country_name")
        if country and not original_country_name:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "country",
                    "value": str(country),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        country_code = data.get("country_code") or data.get("countryCode")
        if country_code and not original_country_code:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "country_code",
                    "value": str(country_code),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        status = data.get("status")
        if status and not connectivity_status and not processing_status:
            formatted_response.append(
                {
                    "source": "hlr",
                    "type": "status",
                    "value": str(status),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        # Ensure type is consistently set to "hlr" for all items
        for item in formatted_response:
            item["type"] = "hlr"

        return formatted_response
