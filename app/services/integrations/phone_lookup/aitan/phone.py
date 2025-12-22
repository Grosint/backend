"""
AITAN Phone Lookup Service Module

This module handles all phone-related lookups for AITAN Labs API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class AITANPhoneService:
    """Service for AITAN Labs phone lookup API integration"""

    # Configuration mapping lookup types to functions
    LOOKUP_CONFIG = {
        "phone-lookup": [
            "mobile_to_profile",
            # "mobile_prefill",
            "mobile_address",
            "mobile_to_vpa_advance",
        ],
        "bank-lookup": [
            "mobile_to_vpa_advance",
        ],
    }

    def __init__(self, parent_service):
        """
        Initialize phone service

        Args:
            parent_service: The parent AITANService instance (for accessing client, base_url, etc.)
        """
        self.parent = parent_service
        self.client = parent_service.client
        self.base_url = parent_service.base_url

    async def search_phone(
        self, country_code: str, phone: str, lookup_type: str = "phone-lookup"
    ) -> dict[str, Any]:
        """
        Search phone number using AITAN API based on lookup type configuration

        Args:
            country_code: Country code (e.g., "+91")
            phone: Phone number
            lookup_type: Type of lookup (phone-lookup, bank-lookup)
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
                            # Recursively remove _raw_response from nested data structures
                            data = self._remove_raw_response_recursive(data)
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
                formatted_response = self._process_mobile_address(data["result"])
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
                formatted_response = self._process_mobile_to_vpa_advance(data["result"])
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
        """Process mobile profile response - preserve all metadata"""
        data = results.get("details", {})
        personal_info = data.get("personal_info", {})

        # Preserve personal info with all fields
        user_info = {
            "name": personal_info.get("full_name"),
            "dob": personal_info.get("dob"),
            "age": personal_info.get("age"),
            "income": personal_info.get("total_income"),
            "occupation": personal_info.get("occupation"),
            "gender": personal_info.get("gender"),
        }

        # Preserve email info with metadata
        email_list = []
        for email in data.get("email_info", []):
            if email and email.get("email_address"):
                email_list.append(
                    {
                        "email": email.get("email_address"),
                        "reported_date": email.get("reported_date"),
                    }
                )

        # Preserve address info with metadata
        address_list = []
        for address in data.get("address_info", []):
            if address and address.get("address"):
                address_list.append(
                    {
                        "address": address.get("address", ""),
                        "pincode": address.get("postal"),
                        "state": address.get("state"),
                        "type": address.get("type"),
                        "reported_date": address.get("reported_date"),
                    }
                )

        # Preserve phone info with all metadata
        phone_list = []
        for phone in data.get("phone_info", []):
            if phone and phone.get("number"):
                phone_list.append(
                    {
                        "number": phone.get("number"),
                        "reported_date": phone.get("reported_date"),
                        "type_code": phone.get("type_code"),
                    }
                )

        # Preserve identity info with structure
        identity_info = {}
        if "identity_info" in data:
            doc_data = data.get("identity_info", {})
            for doc_type, doc_info_list in doc_data.items():
                if isinstance(doc_info_list, list) and doc_info_list:
                    # Get all identity numbers, not just the first one
                    id_numbers = []
                    for doc_info in doc_info_list:
                        if isinstance(doc_info, dict) and doc_info.get("id_number"):
                            id_numbers.append(doc_info.get("id_number"))
                    if id_numbers:
                        identity_info[doc_type] = id_numbers

        return {
            "user_info": user_info,
            "email_list": email_list,
            "phone_list": phone_list,
            "address_list": address_list,
            "identity_info": identity_info,
        }

    def _process_mobile_address(self, result: dict) -> dict:
        """Process mobile address response - preserve all metadata"""
        # Preserve ecommerce addresses with all metadata
        ecommerce_address_list = []
        addresses = result.get("addresses", [])
        for address in addresses:
            if address and address.get("address"):
                ecommerce_address_list.append(
                    {
                        "address": address.get("address", ""),
                        "category": address.get("category"),
                        "date": address.get("date"),
                        "confidence_score": address.get("confidence_score"),
                        "first_seen": address.get("first_seen"),
                        "last_seen": address.get("last_seen"),
                    }
                )

        return {
            "ecommerce_address_list": ecommerce_address_list,
        }

    def _process_mobile_to_vpa_advance(self, result: dict) -> dict:
        """Process mobile to VPA advance response - preserve all metadata"""
        # Preserve bank/VPA info with all fields
        bank_info = {
            "mobile_number": result.get("mobile_number"),
            "name": result.get("name"),
            "ifsc": result.get("ifsc"),
            "vpa": result.get("vpa"),
            "account_type": result.get("account_type"),
            "entity_type": result.get("entity_type"),
        }

        # Extract and preserve IFSC details if available
        ifsc_details = {}
        if "ifsc_details" in result and result["ifsc_details"]:
            ifsc_details = self._flatten_data_recursively(result["ifsc_details"], "", 1)

        return {
            "bank_info": {**bank_info, **ifsc_details},
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

    def _normalize_phone_number(self, phone: str) -> str:
        """Normalize phone number by removing prefixes (0, 91, +91)"""
        if not phone:
            return ""
        # Remove all non-digit characters first, then remove prefixes
        digits_only = "".join(filter(str.isdigit, phone))

        # Remove common prefixes
        if digits_only.startswith("91") and len(digits_only) > 10:
            digits_only = digits_only[2:]
        elif digits_only.startswith("0") and len(digits_only) > 10:
            digits_only = digits_only[1:]

        return digits_only

    def _map_type_code(self, type_code: str) -> str:
        """Map type_code to human-readable format"""
        type_code_mapping = {
            "H": "HOME",
            "M": "MOBILE",
            "T": "TELEPHONE",
            "O": "OFFICE",
        }
        return type_code_mapping.get(type_code, type_code)

    def _normalize_address(self, address: str) -> str:
        """Normalize address for deduplication by removing extra spaces and converting to lowercase"""
        if not address:
            return ""
        # Remove extra spaces, convert to lowercase, and strip
        normalized = " ".join(address.lower().split())
        return normalized

    def _format_aitan_response(
        self, data: dict, func_name: str
    ) -> list[dict[str, Any]]:
        """Format AITAN response to standard format with metadata and groupBy"""
        formatted_response = []
        seen_phones = set()  # Track normalized phone numbers for deduplication
        seen_emails = set()  # Track emails for deduplication (case-insensitive)
        seen_addresses = set()  # Track normalized addresses for deduplication

        # Extract user info (personal details)
        if "user_info" in data:
            user_info = data["user_info"]

            # Name
            if user_info.get("name"):
                formatted_response.append(
                    {
                        "source": "name",
                        "type": "personal_details",
                        "value": user_info["name"],
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            # DOB
            if user_info.get("dob"):
                formatted_response.append(
                    {
                        "source": "dob",
                        "type": "personal_details",
                        "value": user_info["dob"],
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            # Age
            if user_info.get("age"):
                formatted_response.append(
                    {
                        "source": "age",
                        "type": "personal_details",
                        "value": str(user_info["age"]),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            # Gender
            if user_info.get("gender"):
                formatted_response.append(
                    {
                        "source": "gender",
                        "type": "personal_details",
                        "value": user_info["gender"],
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            # Occupation
            if user_info.get("occupation"):
                formatted_response.append(
                    {
                        "source": "occupation",
                        "type": "personal_details",
                        "value": user_info["occupation"],
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            # Income
            if user_info.get("income"):
                formatted_response.append(
                    {
                        "source": "income",
                        "type": "personal_details",
                        "value": str(user_info["income"]),
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

        # Extract emails with metadata (deduplicate)
        if "email_list" in data:
            for email_item in data["email_list"]:
                email = email_item.get("email")
                if email:
                    email_lower = email.lower()
                    if email_lower not in seen_emails:
                        seen_emails.add(email_lower)
                        entry = {
                            "source": "aitan",
                            "type": "email",
                            "value": email,
                            "showSource": False,
                            "category": "TEXT",
                            "groupBy": "contact_details",
                        }
                        # Add metadata if available
                        if email_item.get("reported_date"):
                            entry["metadata"] = {
                                "reported_date": email_item["reported_date"],
                            }
                        formatted_response.append(entry)

        # Extract phone numbers with metadata (deduplicate and normalize)
        if "phone_list" in data:
            for phone_item in data["phone_list"]:
                phone_number = phone_item.get("number")
                if phone_number:
                    # Normalize phone number for deduplication
                    normalized_phone = self._normalize_phone_number(phone_number)

                    # Only add if we haven't seen this normalized number
                    if normalized_phone and normalized_phone not in seen_phones:
                        seen_phones.add(normalized_phone)

                        # Use normalized phone (without prefix) as the value
                        entry = {
                            "source": "aitan",
                            "type": "phone",
                            "value": normalized_phone,
                            "showSource": False,
                            "category": "TEXT",
                            "groupBy": "contact_details",
                        }
                        # Add metadata if available
                        metadata = {}
                        if phone_item.get("reported_date"):
                            metadata["reported_date"] = phone_item["reported_date"]
                        if phone_item.get("type_code"):
                            # Map type_code to human-readable format
                            metadata["type_code"] = self._map_type_code(
                                phone_item["type_code"]
                            )
                        if metadata:
                            entry["metadata"] = metadata
                        formatted_response.append(entry)

        # Extract addresses with metadata
        if "address_list" in data:
            for address_item in data["address_list"]:
                if address_item.get("address"):
                    address_str = address_item.get("address", "")
                    if address_item.get("state"):
                        address_str += f", {address_item['state']}"
                    if address_item.get("pincode"):
                        address_str += f" - {address_item['pincode']}"

                    entry = {
                        "source": "aitan",
                        "type": "location",
                        "value": address_str,
                        "showSource": False,
                        "category": "TEXT",
                        "groupBy": "address_details",
                    }
                    # Add metadata if available
                    metadata = {}
                    if address_item.get("reported_date"):
                        metadata["reported_date"] = address_item["reported_date"]
                    if address_item.get("type"):
                        metadata["address_type"] = address_item["type"]
                    if address_item.get("pincode"):
                        metadata["pincode"] = address_item["pincode"]
                    if address_item.get("state"):
                        metadata["state"] = address_item["state"]
                    if metadata:
                        entry["metadata"] = metadata
                    formatted_response.append(entry)

        # Extract ecommerce addresses with metadata (deduplicate)
        if "ecommerce_address_list" in data:
            for address_item in data["ecommerce_address_list"]:
                address = address_item.get("address")
                if address:
                    # Normalize address for deduplication
                    normalized_address = self._normalize_address(address)

                    # Only add if we haven't seen this normalized address
                    if normalized_address and normalized_address not in seen_addresses:
                        seen_addresses.add(normalized_address)

                        entry = {
                            "source": "aitan",
                            "type": "location",
                            "value": address,  # Use original address, not normalized
                            "showSource": False,
                            "category": "TEXT",
                            "groupBy": "address_details",
                        }
                        # Add metadata if available
                        metadata = {}
                        if address_item.get("category"):
                            metadata["category"] = address_item["category"]
                        if address_item.get("date"):
                            metadata["date"] = address_item["date"]
                        if address_item.get("confidence_score") is not None:
                            metadata["confidence_score"] = address_item[
                                "confidence_score"
                            ]
                        if address_item.get("first_seen"):
                            metadata["first_seen"] = address_item["first_seen"]
                        if address_item.get("last_seen"):
                            metadata["last_seen"] = address_item["last_seen"]
                        if metadata:
                            entry["metadata"] = metadata
                        formatted_response.append(entry)

        # Extract bank/VPA information
        if "bank_info" in data:
            bank_info = data["bank_info"]

            # VPA (Virtual Payment Address)
            if bank_info.get("vpa"):
                entry = {
                    "source": "aitan",
                    "type": "vpa",
                    "value": bank_info["vpa"],
                    "showSource": False,
                    "category": "TEXT",
                    "groupBy": "bank_details",
                }
                metadata = {}
                if bank_info.get("name"):
                    metadata["account_holder_name"] = bank_info["name"]
                if bank_info.get("mobile_number"):
                    metadata["mobile_number"] = bank_info["mobile_number"]
                if bank_info.get("account_type"):
                    metadata["account_type"] = bank_info["account_type"]
                if bank_info.get("entity_type"):
                    metadata["entity_type"] = bank_info["entity_type"]
                if metadata:
                    entry["metadata"] = metadata
                formatted_response.append(entry)

            # IFSC Code
            if bank_info.get("ifsc"):
                entry = {
                    "source": "aitan",
                    "type": "ifsc",
                    "value": bank_info["ifsc"],
                    "showSource": False,
                    "category": "TEXT",
                    "groupBy": "bank_details",
                }
                metadata = {}
                if bank_info.get("name"):
                    metadata["account_holder_name"] = bank_info["name"]
                if bank_info.get("mobile_number"):
                    metadata["mobile_number"] = bank_info["mobile_number"]
                if bank_info.get("account_type"):
                    metadata["account_type"] = bank_info["account_type"]
                # Add any additional IFSC details from flattened data
                for key, value in bank_info.items():
                    if (
                        key
                        not in [
                            "vpa",
                            "ifsc",
                            "name",
                            "mobile_number",
                            "account_type",
                            "entity_type",
                        ]
                        and value
                    ):
                        metadata[key] = value
                if metadata:
                    entry["metadata"] = metadata
                formatted_response.append(entry)

            # Account Type (if VPA or IFSC not present, still show account type)
            if (
                bank_info.get("account_type")
                and not bank_info.get("vpa")
                and not bank_info.get("ifsc")
            ):
                formatted_response.append(
                    {
                        "source": "aitan",
                        "type": "account_type",
                        "value": bank_info["account_type"],
                        "showSource": False,
                        "category": "TEXT",
                        "groupBy": "bank_details",
                    }
                )

            # Account Holder Name (if available and not already included)
            if bank_info.get("name"):
                # Check if name is not already in personal_details
                name_in_personal = any(
                    item.get("type") == "personal_details"
                    and item.get("source") == "name"
                    for item in formatted_response
                )
                if not name_in_personal:
                    formatted_response.append(
                        {
                            "source": "name",
                            "type": "personal_details",
                            "value": bank_info["name"],
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

        # Extract identity documents
        if "identity_info" in data:
            identity_info = data["identity_info"]
            for doc_type, id_numbers in identity_info.items():
                if isinstance(id_numbers, list):
                    for id_number in id_numbers:
                        if id_number:
                            # Map document type to standard type
                            type_mapping = {
                                "pan_number": "pan",
                                "aadhaar_number": "aadhaar",
                                "driving_license": "driving_license",
                                "voter_id": "voter_id",
                                "passport_number": "passport",
                                "ration_card": "ration_card",
                                "other_id": "other_id",
                            }
                            doc_type_standard = type_mapping.get(doc_type, doc_type)

                            formatted_response.append(
                                {
                                    "source": "aitan",
                                    "type": doc_type_standard,
                                    "value": id_number,
                                    "showSource": False,
                                    "category": "TEXT",
                                    "groupBy": "identity_details",
                                }
                            )

        return formatted_response
