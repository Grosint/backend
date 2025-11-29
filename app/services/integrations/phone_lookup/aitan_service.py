from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class AITANService:
    """Service for AITAN Labs API integration with configuration-based routing"""

    # Configuration mapping lookup types to functions
    LOOKUP_CONFIG = {
        "phone-lookup": [
            "mobile_to_profile",
            "mobile_prefill",
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

    async def search_phone(
        self, country_code: str, phone: str, lookup_type: str = "phone-lookup"
    ) -> dict[str, Any]:
        """
        Search phone number using AITAN API based on lookup type configuration

        Args:
            country_code: Country code (e.g., "+91")
            phone: Phone number
            lookup_type: Type of lookup (phone-lookup, vehicle-lookup, bank-lookup)
        """
        try:
            logger.info(
                f"AITAN: Searching {country_code}{phone} with lookup_type={lookup_type}"
            )

            # Get functions to call based on lookup type
            functions_to_call = self.LOOKUP_CONFIG.get(
                lookup_type, self.LOOKUP_CONFIG["phone-lookup"]
            )

            # Call all configured functions in parallel
            import asyncio

            tasks = []
            executed_function_names = []  # Track function names in same order as tasks
            for func_name in functions_to_call:
                if hasattr(self, f"_{func_name}"):
                    if func_name in [
                        "mobile_to_profile",
                        "mobile_prefill",
                        "mobile_address",
                        "mobile_to_vpa_advance",
                    ]:
                        tasks.append(getattr(self, f"_{func_name}")(phone))
                        executed_function_names.append(func_name)
                    else:
                        # For other functions, we'll need different parameters
                        # For now, skip if not phone-based
                        logger.warning(
                            f"AITAN: Function {func_name} not applicable for phone search"
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
                            # Format data to standard format
                            formatted = self._format_aitan_response(data, func_name)
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
            logger.error(f"AITAN search failed: {e}")
            return {
                "found": False,
                "source": "aitan",
                "error": str(e),
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    async def _mobile_to_profile(self, phone_number: str) -> dict[str, Any]:
        """Mobile to profile lookup"""
        try:
            url = f"{self.base_url}/api/mobile/v1/mobile-to-profile"
            headers = {
                "content-type": "application/json",
                "apiKey": settings.AITAN_API_KEY,
            }
            payload = {
                "mobile": phone_number,
                "consent": "yes",
                "consent_text": "I give my consent to check my mobile details",
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

            if data.get("result") and len(data["result"]):
                formatted_response = self._process_mobile_profile(data["result"])
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": None,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"AITAN mobile_to_profile failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _mobile_prefill(self, phone_number: str) -> dict[str, Any]:
        """Mobile prefill lookup"""
        try:
            url = f"{self.base_url}/api/mobile/v1/mobile-prefill"
            headers = {
                "content-type": "application/json",
                "apiKey": settings.AITAN_API_KEY,
            }
            payload = {
                "mobile": phone_number,
                "name_lookup": 0,
                "first_name": "",
                "last_name": "",
                "consent": "yes",
                "consent_text": "I give my consent to check my mobile details",
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

            if data.get("result") and len(data["result"]):
                formatted_response = self._process_mobile_prefill(data["result"])
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": None,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"AITAN mobile_prefill failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _mobile_address(self, phone_number: str) -> dict[str, Any]:
        """Mobile address lookup"""
        try:
            url = f"{self.base_url}/api/mobile/v1/mobile-address"
            headers = {
                "content-type": "application/json",
                "apiKey": settings.AITAN_API_KEY,
            }
            payload = {
                "mobile": phone_number,
                "consent": "yes",
                "consent_text": "I give my consent to check my mobile details",
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
                formatted_response = {
                    "ecommerce_address": data["result"].get("addresses", [])
                }
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": None,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"AITAN mobile_address failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _mobile_to_vpa_advance(self, phone_number: str) -> dict[str, Any]:
        """Mobile to VPA advance lookup"""
        try:
            url = f"{self.base_url}/upi/v1/mobile-to-vpa-advance"
            headers = {
                "content-type": "application/json",
                "apiKey": settings.AITAN_API_KEY,
            }
            payload = {
                "mobile": phone_number,
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
                result_data = data["result"]
                # Extract and flatten IFSC details if available
                ifsc_details = {}
                if "ifsc_details" in result_data and result_data["ifsc_details"]:
                    ifsc_details = self._flatten_data_recursively(
                        result_data["ifsc_details"], "", 1
                    )
                    result_data.pop("ifsc_details", None)
                formatted_response = {"bank_info": {**result_data, **ifsc_details}}
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": None,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"AITAN mobile_to_vpa_advance failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    def _process_mobile_profile(self, results: dict) -> dict:
        """Process mobile profile response"""
        data = results.get("details", {})
        personal_info = data.get("personal_info", {})
        user_info = {
            "name": personal_info.get("full_name", "N/A"),
            "dob": personal_info.get("dob", "N/A"),
            "age": personal_info.get("age", "N/A"),
            "income": personal_info.get("total_income", "N/A"),
            "occupation": personal_info.get("occupation", "N/A"),
            "gender": personal_info.get("gender", "N/A"),
        }

        email_list = []
        for email in data.get("email_info", []):
            if email:
                email_list.append({"email": email.get("email_address", "N/A")})

        address_list = []
        for address in data.get("address_info", []):
            if address:
                formatted_address = {
                    "address": address.get("address", ""),
                    "pincode": address.get("postal", "N/A"),
                    "state": address.get("state", "N/A"),
                    "type": address.get("type", "N/A"),
                    "date_of_reporting": address.get("reported_date", "N/A"),
                }
                address_list.append(formatted_address)

        alternate_phone_list = []
        for phone in data.get("phone_info", []):
            if phone:
                alternate_phone_list.append(
                    {"phone_number": phone.get("number", "N/A")}
                )

        other_documents = {}
        if "identity_info" in data:
            doc_data = data.get("identity_info", {})
            for doc_type, doc_info_list in doc_data.items():
                if isinstance(doc_info_list, list) and doc_info_list:
                    doc_info = doc_info_list[0]
                    if isinstance(doc_info, dict) and "id_number" in doc_info:
                        other_documents[doc_type] = doc_info.get("id_number", "N/A")

        return {
            "user_info": user_info,
            "email_list": email_list,
            "alternate_phone_list": alternate_phone_list,
            "address_list": address_list,
            "other_documents": other_documents,
        }

    def _process_mobile_prefill(self, data: dict) -> dict:
        """Process mobile prefill response"""
        user_info = {
            "name": data.get("name", "N/A"),
            "dob": data.get("dob", "N/A"),
            "email": data.get("email", "N/A"),
            "age": data.get("age", "N/A"),
            "gender": data.get("gender", "N/A"),
        }

        address_list = []
        for address in data.get("address", []):
            formatted_address = {
                "address": (
                    (address.get("first_line_of_address", "") or "")
                    + " "
                    + (address.get("second_line_of_address", "") or "")
                    + " "
                    + (address.get("third_line_of_address", "") or "")
                ),
                "city": address.get("city", "N/A"),
                "pincode": address.get("postal_code", "N/A"),
                "state": address.get("state", "N/A"),
                "date_of_reporting": address.get("reported_date", "N/A"),
            }
            address_list.append(formatted_address)

        other_documents = {}
        excluded_keys = ["name", "dob", "age", "gender", "email", "address", "score"]

        for key, value in data.items():
            if key not in excluded_keys:
                if value is None:
                    continue
                elif isinstance(value, (dict, list)):
                    flattened_data = self._flatten_data_recursively(value, key, 1)
                    other_documents.update(flattened_data)
                else:
                    other_documents[key] = value

        return {
            "user_info": user_info,
            "address_list": address_list,
            "other_documents": other_documents,
        }

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

    def _format_aitan_response(
        self, data: dict, func_name: str
    ) -> list[dict[str, Any]]:
        """Format AITAN response to standard format"""
        formatted_response = []

        # Extract user info
        if "user_info" in data:
            user_info = data["user_info"]
            if user_info.get("name") and user_info["name"] != "N/A":
                formatted_response.append(
                    {
                        "source": "aitan",
                        "type": "name",
                        "value": user_info["name"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        # Extract emails
        if "email_list" in data:
            for email_item in data["email_list"]:
                if email_item.get("email") and email_item["email"] != "N/A":
                    formatted_response.append(
                        {
                            "source": "aitan",
                            "type": "email",
                            "value": email_item["email"],
                            "showSource": False,
                            "category": "TEXT",
                        }
                    )

        # Extract addresses
        if "address_list" in data:
            for address_item in data["address_list"]:
                if address_item.get("address") and address_item["address"] != "N/A":
                    address_str = address_item.get("address", "")
                    if address_item.get("city") and address_item["city"] != "N/A":
                        address_str += f", {address_item['city']}"
                    if address_item.get("state") and address_item["state"] != "N/A":
                        address_str += f", {address_item['state']}"
                    if address_item.get("pincode") and address_item["pincode"] != "N/A":
                        address_str += f" - {address_item['pincode']}"

                    formatted_response.append(
                        {
                            "source": "aitan",
                            "type": "location",
                            "value": address_str,
                            "showSource": False,
                            "category": "TEXT",
                        }
                    )

        # Extract alternate phones
        if "alternate_phone_list" in data:
            for phone_item in data["alternate_phone_list"]:
                if (
                    phone_item.get("phone_number")
                    and phone_item["phone_number"] != "N/A"
                ):
                    formatted_response.append(
                        {
                            "source": "aitan",
                            "type": "phone",
                            "value": phone_item["phone_number"],
                            "showSource": False,
                            "category": "TEXT",
                        }
                    )

        # Add raw data for other fields
        if formatted_response:
            formatted_response.append(
                {
                    "source": "aitan",
                    "type": "raw_data",
                    "value": str(data),
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        return formatted_response
