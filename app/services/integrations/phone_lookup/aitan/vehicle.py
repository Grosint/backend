"""
AITAN Vehicle Lookup Service Module

This module handles all vehicle-related lookups for AITAN Labs API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings

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

logger = logging.getLogger(__name__)


class AITANVehicleService:
    """Service for AITAN Labs vehicle lookup API integration"""

    # Configuration mapping lookup types to functions
    LOOKUP_CONFIG = {
        "vehicle-lookup": [
            "rc_advance",
            "challan_advance",
            "chassis_to_rc",
            "mobile_to_fasttag_history",
        ],
    }

    def __init__(self, parent_service):
        """
        Initialize vehicle service

        Args:
            parent_service: The parent AITANService instance (for accessing client, base_url, etc.)
        """
        self.parent = parent_service
        self.client = parent_service.client
        self.base_url = parent_service.base_url
        self.base_url_com = parent_service.base_url_com

    async def search_vehicle(
        self,
        vehicle_number: str,
        lookup_type: str = "vehicle-lookup",
        chassis_number: str | None = None,
    ) -> dict[str, Any]:
        """
        Search vehicle using AITAN API based on lookup type configuration

        Args:
            vehicle_number: Vehicle registration number
            lookup_type: Type of lookup (vehicle-lookup)
            chassis_number: Chassis number (optional, for chassis_to_rc lookup)
        """
        try:
            logger.info(
                f"AITAN: Searching vehicle {vehicle_number} with lookup_type={lookup_type}"
            )

            # Get functions to call based on lookup type
            functions_to_call = self.LOOKUP_CONFIG.get(
                lookup_type, self.LOOKUP_CONFIG["vehicle-lookup"]
            )

            # Call all configured functions in parallel
            tasks = []
            executed_function_names = []  # Track function names in same order as tasks
            for func_name in functions_to_call:
                if hasattr(self, f"_{func_name}"):
                    if func_name in [
                        "rc_advance",
                        "challan_advance",
                        "mobile_to_fasttag_history",
                    ]:
                        tasks.append(getattr(self, f"_{func_name}")(vehicle_number))
                        executed_function_names.append(func_name)
                    elif func_name == "chassis_to_rc":
                        # Use chassis_number if provided, otherwise use vehicle_number
                        chassis = chassis_number or vehicle_number
                        tasks.append(getattr(self, f"_{func_name}")(chassis))
                        executed_function_names.append(func_name)
                    else:
                        logger.warning(
                            f"AITAN: Function {func_name} not applicable for vehicle search"
                        )

            if not tasks:
                return {
                    "found": False,
                    "source": "aitan",
                    "data": None,
                    "confidence": 0.0,
                    "error": f"No applicable functions for lookup_type={lookup_type}",
                }

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            combined_data = []
            found_any = False
            raw_responses = {}

            for result, func_name in zip(
                results, executed_function_names, strict=False
            ):
                if isinstance(result, Exception):
                    logger.error(f"AITAN {func_name} failed: {result}")
                    raw_responses[func_name] = {"error": str(result)}
                    continue

                if isinstance(result, dict):
                    raw_responses[func_name] = result.get("_raw_response", result)
                    if result.get("found", False):
                        found_any = True
                        data = result.get("data", {})
                        if data:
                            # Recursively remove _raw_response from nested data structures
                            data = self._remove_raw_response_recursive(data)
                            # Format data to standard format
                            formatted = self._format_aitan_vehicle_response(
                                data, func_name
                            )
                            combined_data.extend(formatted)

            if found_any and combined_data:
                return {
                    "found": True,
                    "source": "aitan",
                    "data": combined_data,
                    "confidence": 0.8,
                    "_raw_response": raw_responses,
                }
            else:
                return {
                    "found": False,
                    "source": "aitan",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": raw_responses,
                }

        except Exception as e:
            logger.error(f"AITAN vehicle search failed: {e}")
            return {
                "found": False,
                "source": "aitan",
                "error": str(e),
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    async def _rc_advance(self, vehicle_number: str) -> dict[str, Any]:
        """RC advance lookup"""
        try:
            url = f"{self.base_url_com}/api/v1/private/rc-advance"
            headers = {
                "content-type": "application/json",
                "apiKey": settings.AITAN_API_KEY,
            }
            payload = {
                "reg_no": vehicle_number,
                "consent": "yes",
                "consent_text": "I hear by declare my consent agreement for fetching my information via AITAN Labs API",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="aitan_api",
            )

            data = response.json()
            raw_response = data

            if "result" in data and len(data["result"]):
                formatted_response = self._process_rc_advance(data["result"])
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": {
                        "Vehicle Info": {"Message": "Data Not Found"},
                        "Owner Info": {"Message": "Data Not Found"},
                        "Insurance Info": {"Message": "Data Not Found"},
                    },
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"AITAN rc_advance failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _challan_advance(self, vehicle_number: str) -> dict[str, Any]:
        """Challan advance lookup"""
        try:
            url = f"{self.base_url}/api/v1/challan-plus"
            headers = {
                "content-type": "application/json",
                "apiKey": settings.AITAN_API_KEY,
            }
            payload = {
                "reg_no": vehicle_number,
                "consent": "yes",
                "consent_text": "I give my consent to to check my challan details",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="aitan_api",
            )

            data = response.json()
            raw_response = data

            if "result" in data and len(data["result"]):
                formatted_response = self._process_challan_advance(data["result"])
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": {"Challan Info": {"Message": "Data Not Found"}},
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"AITAN challan_advance failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _chassis_to_rc(self, chassis_number: str) -> dict[str, Any]:
        """Chassis to RC lookup"""
        try:
            url = f"{self.base_url_com}/api/v1/chasis-to-rc"
            headers = {
                "content-type": "application/json",
                "apiKey": settings.AITAN_API_KEY,
            }
            payload = {
                "chassis_no": chassis_number,
                "consent": "Y",
                "consent_text": "I hear by declare my consent agreement for fetching my information via AITAN Labs API",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="aitan_api",
            )

            data = response.json()
            raw_response = data

            if "result" in data:
                formatted_response = self._process_chassis_to_rc(data["result"])
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": {"Vehicle Info": {"Message": "Data Not Found"}},
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"AITAN chassis_to_rc failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _mobile_to_fasttag_history(self, vehicle_number: str) -> dict[str, Any]:
        """Mobile to FastTag history lookup"""
        try:
            url = f"{self.base_url_com}/api/v1/fastag/fastag-history"
            headers = {
                "content-type": "application/json",
                "apiKey": settings.AITAN_API_KEY,
            }
            payload = {
                "reg_no": vehicle_number,
                "consent": "Y",
                "consent_text": "I hear by declare my consent agreement for fetching my information via AITAN Labs API",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="aitan_api",
            )

            data = response.json()
            raw_response = data

            if "result" in data and len(data["result"]):
                formatted_response = self._process_fasttag_history(data["result"])
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": {"fasttag_history": {"Message": "Data Not Found"}},
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"AITAN mobile_to_fasttag_history failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    def _process_rc_advance(self, result: dict) -> dict:
        """Process RC advance response"""
        final_data = {}
        for key, value in result.items():
            if not self._is_valid_value_aitan(value):
                value = "Not Available"

            key_value = key.replace("_", " ").upper()

            if key in VEHICLE_INFO_AITAN:
                final_data.setdefault("Vehicle Info", {})[key_value] = value
            elif key in OWNER_INFO_AITAN:
                final_data.setdefault("Owner Info", {})[key_value] = (
                    self._construct_address_aitan(value)
                    if key in ["split_permanent_address", "split_present_address"]
                    else value
                )
            elif key == "vehicle_insurance_details" and isinstance(value, dict):
                # Handle insurance details
                insurance_info = value
                for ins_key, ins_value in insurance_info.items():
                    ins_key_value = ins_key.replace("_", " ").upper()
                    if ins_key in INSURANCE_INFO_AITAN:
                        final_data.setdefault("Insurance Info", {})[
                            ins_key_value
                        ] = ins_value

        return final_data

    def _process_challan_advance(self, result: dict) -> dict:
        """Process challan advance response"""
        # Handle nested result structure
        challan_data = (
            result.get("data")
            if "data" in result
            else result.get("result", {}).get("data", [])
        )

        if not challan_data or not isinstance(challan_data, list):
            return {"Challan Info": {"Message": "Data Not Found"}}

        processed_data = []
        for challan in challan_data:
            if not isinstance(challan, dict):
                continue

            processed_challan = {}
            self._process_dict_for_challan(challan, processed_challan)
            if processed_challan:
                processed_data.append(processed_challan)

        return {
            "Challan Info": (
                processed_data if processed_data else [{"Message": "Data Not Found"}]
            )
        }

    def _process_chassis_to_rc(self, result: dict) -> dict:
        """Process chassis to RC response"""
        return {"Vehicle Info": result}

    def _process_fasttag_history(self, result: dict) -> dict:
        """Process FastTag history response"""
        transactions = result.get("transactions", [])
        return {
            "fasttag_history": (
                transactions if transactions else [{"Message": "Data Not Found"}]
            )
        }

    def _is_valid_value_aitan(self, value: Any) -> bool:
        """Check if value is valid"""
        return (
            value is not None
            and value != ""
            and (not isinstance(value, list) or len(value) > 0)
        )

    def _construct_address_aitan(self, data: dict) -> str:
        """Construct address from data"""
        fields = ["address_line", "city", "district", "state", "pincode", "country"]
        return ", ".join(
            filter(
                None,
                [
                    self._get_first_non_empty_value_aitan(data.get(field))
                    for field in fields
                ],
            )
        )

    def _get_first_non_empty_value_aitan(self, value: Any) -> str | None:
        """Get first non-empty value from list or return value"""
        if isinstance(value, list):
            return next((v for v in value if v), None)
        return value or None

    def _process_dict_for_challan(
        self, input_dict: dict, output_dict: dict, prefix: str = ""
    ):
        """Process dictionary for challan data recursively"""
        for key, value in input_dict.items():
            # Skip null values
            if value is None:
                continue

            # Format key from camelCase to uppercase with spaces
            formatted_key = self._format_key_for_challan(key)
            if prefix:
                formatted_key = f"{prefix} {formatted_key}"

            # Handle nested dictionaries and lists recursively
            if isinstance(value, (dict, list)):
                flattened_data = self._flatten_data_recursively(value, formatted_key, 1)
                output_dict.update(flattened_data)
            else:
                output_dict[formatted_key] = value

    def _format_key_for_challan(self, key: str) -> str:
        """Convert camelCase to words with spaces"""
        result = key[0].upper()
        for char in key[1:]:
            if char.isupper():
                result += " " + char
            else:
                result += char
        return result

    def _flatten_data_recursively(
        self, data: Any, prefix: str = "", counter: int = 1
    ) -> dict:
        """Recursively flatten dictionaries and lists, ignoring null values"""
        flattened = {}

        if data is None:
            return flattened

        if isinstance(data, dict):
            for key, value in data.items():
                if value is None:
                    continue

                new_key = f"{prefix} {key}".strip() if prefix else key

                if isinstance(value, (dict, list)):
                    nested_flattened = self._flatten_data_recursively(
                        value, new_key, counter
                    )
                    flattened.update(nested_flattened)
                else:
                    flattened[new_key] = value

        elif isinstance(data, list):
            for _i, item in enumerate(data, 1):
                if item is None:
                    continue

                new_key = f"{prefix} {counter}" if prefix else f"item_{counter}"

                if isinstance(item, (dict, list)):
                    nested_flattened = self._flatten_data_recursively(item, new_key, 1)
                    flattened.update(nested_flattened)
                else:
                    flattened[new_key] = item
                counter += 1

        return flattened

    def _remove_raw_response_recursive(self, data: Any) -> Any:
        """Recursively remove _raw_response from nested dictionaries"""
        if isinstance(data, dict):
            # Remove _raw_response key if present
            cleaned = {k: v for k, v in data.items() if k != "_raw_response"}
            # Recursively clean nested dictionaries and lists
            return {
                k: self._remove_raw_response_recursive(v) for k, v in cleaned.items()
            }
        elif isinstance(data, list):
            return [self._remove_raw_response_recursive(item) for item in data]
        else:
            return data

    def _format_aitan_vehicle_response(
        self, data: dict, func_name: str
    ) -> list[dict[str, Any]]:
        """Format AITAN vehicle response to standard format"""
        formatted_response = []

        # Handle RC Advance response
        if "Vehicle Info" in data:
            vehicle_info = data["Vehicle Info"]
            for key, value in vehicle_info.items():
                if value and value != "Not Available" and value != "Data Not Found":
                    formatted_response.append(
                        {
                            "source": key.lower().replace(" ", "_"),
                            "type": "vehicle_details",
                            "value": str(value),
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

        if "Owner Info" in data:
            owner_info = data["Owner Info"]
            for key, value in owner_info.items():
                if value and value != "Not Available" and value != "Data Not Found":
                    formatted_response.append(
                        {
                            "source": key.lower().replace(" ", "_"),
                            "type": "owner_details",
                            "value": str(value),
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

        if "Insurance Info" in data:
            insurance_info = data["Insurance Info"]
            for key, value in insurance_info.items():
                if value and value != "Not Available" and value != "Data Not Found":
                    formatted_response.append(
                        {
                            "source": key.lower().replace(" ", "_"),
                            "type": "insurance_details",
                            "value": str(value),
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

        # Handle Challan Info
        if "Challan Info" in data:
            challan_info = data["Challan Info"]
            if isinstance(challan_info, list):
                for challan in challan_info:
                    if isinstance(challan, dict):
                        for key, value in challan.items():
                            if value and value != "Data Not Found":
                                formatted_response.append(
                                    {
                                        "source": "aitan",
                                        "type": "challan",
                                        "value": f"{key}: {value}",
                                        "showSource": False,
                                        "category": "TEXT",
                                        "groupBy": "challan_details",
                                    }
                                )

        # Handle FastTag History
        if "fasttag_history" in data:
            fasttag_history = data["fasttag_history"]
            if isinstance(fasttag_history, list):
                for transaction in fasttag_history:
                    if isinstance(transaction, dict):
                        for key, value in transaction.items():
                            if value and value != "Data Not Found":
                                formatted_response.append(
                                    {
                                        "source": "aitan",
                                        "type": "fasttag",
                                        "value": f"{key}: {value}",
                                        "showSource": False,
                                        "category": "TEXT",
                                        "groupBy": "fasttag_details",
                                    }
                                )

        return formatted_response
