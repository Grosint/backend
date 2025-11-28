from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)

# Constants for response categorization
RESPONSE_CATEGORIES = {"TEXT": "TEXT"}

# Constants for vehicle RC processing
VEHICLE_INFO = [
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

OWNER_INFO = [
    "owner_name",
    "owner_father_name",
    "owner_address",
    "split_permanent_address",
    "split_present_address",
    "owner_mobile",
    "owner_email",
]

INSURANCE_INFO = [
    "insurance_company",
    "insurance_policy_no",
    "insurance_valid_from",
    "insurance_valid_to",
    "insurance_upto",
]

CHALLAN_LIST_INFO = [
    "challan_no",
    "challan_date",
    "violation_type",
    "violation_description",
    "fine_amount",
    "location",
    "status",
    "payment_status",
    "vehicle_no",
    "fastag_id",
    "tag_id",
    "tag_status",
    "tag_issuer",
    "tag_class",
    "tag_validity",
]


class BefiscService:
    """Service for Befisc API integration with configuration-based routing"""

    # Configuration mapping lookup types to functions
    LOOKUP_CONFIG = {
        "phone-lookup": [
            "mobile_advance_profile_basic",
            "mobile_supreme_bank_details",
            "lpg_search",
        ],
        "vehicle-lookup": [
            "rc_search_advance_v3",
            "rc_search_challan_details",
            "rc_fastag_info",
        ],
        "bank-lookup": [
            "bank_search",
            "upi_search",
            "mobile_supreme_bank_details",
        ],
        "pan-lookup": [
            "pan_search",
        ],
        "driving-license-lookup": [
            "driving_license_search",
        ],
        "voter-id-lookup": [
            "voter_id_search",
        ],
    }

    def __init__(self):
        self.name = "BefiscService"
        self.client = ResilientHttpClient()
        self.base_url = "https://prod.befisc.com"
        self.vehicle_url = "https://vehicle-verification.befisc.com"
        self.bank_url = "https://bank-account-verification.befisc.com"
        self.pan_url = "https://pan-all-in-one.befisc.com"
        self.challan_url = "https://challan-details.befisc.com"
        self.fastag_url = "https://fastag.befisc.com"
        self.utility_url = "https://utility.befisc.com"
        self.dl_url = "https://dl-advance.befisc.com"
        self.voter_url = "https://voter.befisc.com"

    async def search_phone(
        self,
        country_code: str,
        phone: str,
        lookup_type: str = "phone-lookup",
        **kwargs,
    ) -> dict[str, Any]:
        """
        Search phone number using Befisc API based on lookup type configuration

        Args:
            country_code: Country code (e.g., "+91")
            phone: Phone number
            lookup_type: Type of lookup (phone-lookup, vehicle-lookup, bank-lookup, etc.)
            **kwargs: Additional parameters for specific lookup types
        """
        try:
            logger.info(
                f"Befisc: Searching {country_code}{phone} with lookup_type={lookup_type}"
            )

            # Get functions to call based on lookup type
            functions_to_call = self.LOOKUP_CONFIG.get(
                lookup_type, self.LOOKUP_CONFIG["phone-lookup"]
            )

            # Call all configured functions in parallel
            import asyncio

            tasks = []
            for func_name in functions_to_call:
                if hasattr(self, f"_{func_name}"):
                    # Determine parameters based on function
                    if func_name in [
                        "mobile_advance_profile_basic",
                        "mobile_supreme_bank_details",
                        "lpg_search",
                    ]:
                        # Phone-based functions
                        name = kwargs.get("name", "")
                        if func_name == "lpg_search":
                            tasks.append(
                                getattr(self, f"_{func_name}")(
                                    phone, is_format_for_osint=True
                                )
                            )
                        elif func_name == "mobile_advance_profile_basic":
                            tasks.append(getattr(self, f"_{func_name}")(phone, name))
                        else:
                            tasks.append(getattr(self, f"_{func_name}")(phone))
                    else:
                        logger.warning(
                            f"Befisc: Function {func_name} not applicable for phone search"
                        )

            if not tasks:
                return {
                    "found": False,
                    "source": "befisc",
                    "data": None,
                    "confidence": 0.0,
                    "error": f"No applicable functions for lookup_type={lookup_type}",
                }

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            combined_data = []
            found_any = False
            raw_responses = {}

            for i, result in enumerate(results):
                func_name = functions_to_call[i]
                if isinstance(result, Exception):
                    logger.error(f"Befisc {func_name} failed: {result}")
                    raw_responses[func_name] = {"error": str(result)}
                    continue

                if isinstance(result, dict):
                    raw_responses[func_name] = result.get("_raw_response", result)
                    if result.get("found", False):
                        found_any = True
                        data = result.get("data", {})
                        if data:
                            # Format data to standard format
                            formatted = self._format_befisc_response(data, func_name)
                            combined_data.extend(formatted)

            if found_any and combined_data:
                return {
                    "found": True,
                    "source": "befisc",
                    "data": combined_data,
                    "confidence": 0.8,
                    "_raw_response": raw_responses,
                }
            else:
                return {
                    "found": False,
                    "source": "befisc",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": raw_responses,
                }

        except Exception as e:
            logger.error(f"Befisc search failed: {e}")
            return {
                "found": False,
                "source": "befisc",
                "error": str(e),
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    async def _mobile_advance_profile_basic(
        self, phone_number: str, name: str = ""
    ) -> dict[str, Any]:
        """Mobile advance profile basic lookup"""
        try:
            url = f"{self.base_url}/KZ97"
            headers = {
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {
                "mobile": phone_number,
                "first_name": name,
                "consent": "Y",
                "consent_text": "We confirm obtaining valid customer consent to access/process their mobile data. Consent remains valid, informed, and unwithdrawn.",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = {
                "user_info": {"Error": "Data Not Found"},
                "address_list": [{"Error": "Data Not Found"}],
                "other_documents": {"Error": "Data Not Found"},
            }
            if "result" in data and len(data["result"]):
                formatted_response = (
                    self._process_mobile_advance_profile_basic_response(data["result"])
                )
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc mobile_advance_profile_basic failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _mobile_supreme_bank_details(self, phone_number: str) -> dict[str, Any]:
        """Mobile supreme bank details lookup"""
        try:
            url = f"{self.base_url}/QL67"
            headers = {
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {
                "mobile": phone_number,
                "consent": "Y",
                "consent_text": "We confirm obtaining valid customer consent to access/process their mobile data. Consent remains valid, informed, and unwithdrawn.",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = {"bank_info": {}}
            if "result" in data and len(data["result"]):
                formatted_response = self._process_mobile_supreme_bank_details_response(
                    data["result"]
                )
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc mobile_supreme_bank_details failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _lpg_search(
        self, phone_number: str, is_format_for_osint: bool = True
    ) -> dict[str, Any]:
        """LPG search by phone number"""
        try:
            url = f"{self.utility_url}/lpg-verification/mobile"
            headers = {
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {
                "mobile": phone_number,
                "consent": "Y",
                "consent_text": "We confirm that we have obtained the consent of the respective customer to fetch their details by using their Mobile Number and the customer is aware of the purpose for which their data is sought for being processed and have given their consent for the same and such consent is currently valid and not withdrawn.",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            if not is_format_for_osint:
                formatted_response = {
                    "lpg_info": [
                        {"Message": "No Gas Connection Registered on this number"}
                    ]
                }
            else:
                formatted_response = [
                    {
                        "source": "LPG Provider",
                        "type": "lpg",
                        "value": "No LPG data found",
                        "showSource": False,
                        "category": RESPONSE_CATEGORIES["TEXT"],
                    }
                ]

            if "result" in data and len(data["result"]):
                formatted_response = self._process_lpg_search(
                    data["result"], is_format_for_osint
                )
                return {
                    "found": True,
                    "data": (
                        formatted_response
                        if is_format_for_osint
                        else {"lpg_info": formatted_response}
                    ),
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": (
                        formatted_response
                        if is_format_for_osint
                        else {"lpg_info": formatted_response}
                    ),
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc lpg_search failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _rc_search_advance_v3(self, vehicle_number: str) -> dict[str, Any]:
        """RC search advance v3"""
        try:
            url = f"{self.vehicle_url}/rc-advance/v3"
            headers = {
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {
                "vehicle_no": vehicle_number,
                "consent": "Y",
                "consent_text": "We confirm that we have obtained the consent of the respective customer to fetch their details by using their RC Number and the customer is aware of the purpose for which their data is sought for being processed and have given their consent for the same and such consent is currently valid and not withdrawn.",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = {}
            if "result" in data and len(data["result"]):
                flatten_resp = self._flatten_dict(data["result"])
                formatted_response = self._process_rc_response(flatten_resp)
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc rc_search_advance_v3 failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _rc_search_challan_details(self, vehicle_number: str) -> dict[str, Any]:
        """RC search challan details"""
        try:
            url = f"{self.challan_url}"
            headers = {
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {
                "vehicle_no": vehicle_number,
                "consent": "Y",
                "consent_text": "I give my consent to challan-details api to check my challan details",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = {
                "Challan Info": [{"Message": "No Challan Data Found"}]
            }
            if "result" in data and len(data["result"]):
                formatted_response = self._process_challan_response(data["result"])
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc rc_search_challan_details failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _rc_fastag_info(self, vehicle_number: str) -> dict[str, Any]:
        """RC FastTag info"""
        try:
            url = f"{self.fastag_url}/"
            headers = {
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {"vehicle_no": vehicle_number}

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = {"Fast Tag Info": {"Error": "No Fast Tag Data Found"}}
            if "result" in data and len(data["result"]):
                formatted_response = self._process_fastatag_response(data["result"])
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc rc_fastag_info failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _bank_search(self, account_no: str, ifsc_code: str) -> dict[str, Any]:
        """Bank account verification search"""
        try:
            url = f"{self.bank_url}/penny-less"
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {
                "account_no": account_no,
                "ifsc_code": ifsc_code,
                "consent": "Y",
                "consent_text": "I give my consent to Bank Account Verification (Penny Less) api to check my bank details",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = self._process_bank_search_response(data)
            if "Error" not in formatted_response:
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc bank_search failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _upi_search(self, upi: str) -> dict[str, Any]:
        """UPI search"""
        try:
            url = f"{self.base_url}/WBII"
            headers = {
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {
                "digital_payment_id": upi,
                "consent": "Y",
                "consent_text": "We confirm obtaining valid customer consent to access/process their digital payment id data. Consent remains valid, informed, and unwithdrawn.",
            }

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = {}
            if "result" in data and len(data["result"]):
                formatted_response = data["result"]
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc upi_search failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _pan_search(self, pan: str) -> dict[str, Any]:
        """PAN search"""
        try:
            url = f"{self.pan_url}/"
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {"pan": pan}

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = self._process_pan_response(data)
            if "Error" not in formatted_response:
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc pan_search failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _driving_license_search(
        self, license_number: str, dob: str
    ) -> dict[str, Any]:
        """Driving license search (dob format: DD-MM-YYYY)"""
        try:
            url = f"{self.dl_url}"
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {"dl_no": license_number, "dob": dob}

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = self._process_license_data(data)
            if "Error" not in formatted_response:
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc driving_license_search failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    async def _voter_id_search(self, epic_number: str) -> dict[str, Any]:
        """Voter ID search (EPIC - Electoral Photo Identity Card)"""
        try:
            url = f"{self.voter_url}"
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authkey": settings.BEFISC_API_KEY,
            }
            payload = {"voter": epic_number}

            response = await self.client.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                circuit_key="befisc_api",
            )

            data = response.json()
            raw_response = data

            formatted_response = self._process_voter_id_data(data)
            if "Error" not in formatted_response:
                return {
                    "found": True,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }
            else:
                return {
                    "found": False,
                    "data": formatted_response,
                    "_raw_response": raw_response,
                }

        except Exception as e:
            logger.error(f"Befisc voter_id_search failed: {e}")
            return {
                "found": False,
                "error": str(e),
                "_raw_response": {"error": str(e)},
            }

    # Processing methods
    def _process_mobile_advance_profile_basic_response(self, data: dict) -> dict:
        """Process mobile advance profile basic response"""
        result = {
            "user_info": {
                "name": data.get("personal_information", {}).get("full_name"),
                "age": data.get("personal_information", {}).get("age"),
                "dob": data.get("personal_information", {}).get("date_of_birth"),
                "income": data.get("personal_information", {}).get("income"),
                "email": (
                    ",".join(
                        [email["value"].lower() for email in data.get("email", [])]
                    )
                    if data.get("email")
                    else ""
                ),
                "mobileNumber": (
                    ", ".join(
                        [phone["value"] for phone in data.get("alternate_phone", [])]
                    )
                    if data.get("alternate_phone")
                    else ""
                ),
            },
            "address_list": [
                {
                    "address": address.get("detailed_address"),
                    "pincode": address.get("pincode"),
                    "state": address.get("state"),
                    "type": address.get("type"),
                    "date_of_reporting": address.get("date_of_reporting"),
                }
                for address in data.get("address", [])
            ],
        }
        result["other_documents"] = {
            key: value[0]["value"] if value else "Not Available"
            for key, value in data.get("document_data", {}).items()
        }

        return result

    def _process_mobile_supreme_bank_details_response(self, data: dict) -> dict:
        """Process mobile supreme bank details response"""
        bank_info = {
            "name": data.get("name"),
            "bank": data.get("bank"),
            "branch": data.get("branch"),
            "center": data.get("center"),
            "district": data.get("district"),
            "state": data.get("state"),
            "address": data.get("address"),
            "contact": data.get("contact"),
            "city": data.get("city"),
        }
        return {"bank_info": bank_info}

    def _process_lpg_search(self, data: list, is_format_for_osint: bool) -> list | dict:
        """Process LPG search response"""
        result = []
        if not is_format_for_osint:
            for item in data:
                result.append(
                    {
                        "gas_provider": item.get("gas_provider", ""),
                        "name": item.get("name", ""),
                        "address": item.get("address", ""),
                        "distributor_code": item.get("distributor_details", {}).get(
                            "distributor_code"
                        ),
                        "distributor_name": item.get("distributor_details", {}).get(
                            "distributor_name"
                        ),
                        "distributor_contact": item.get("distributor_details", {}).get(
                            "distributor_contact"
                        ),
                        "distributor_address": item.get("distributor_details", {}).get(
                            "distributor_address"
                        ),
                    }
                )
            return {"lpg_info": result}
        else:
            for item in data:
                result.append(
                    {
                        "source": "LPG Provider",
                        "type": "lpg",
                        "value": item.get("gas_provider", ""),
                        "showSource": True,
                        "category": RESPONSE_CATEGORIES["TEXT"],
                    }
                )
                result.append(
                    {
                        "source": "Name",
                        "type": "lpg",
                        "value": item.get("name", ""),
                        "showSource": True,
                        "category": RESPONSE_CATEGORIES["TEXT"],
                    }
                )
                result.append(
                    {
                        "source": "Address",
                        "type": "lpg",
                        "value": item.get("address", ""),
                        "showSource": True,
                        "category": RESPONSE_CATEGORIES["TEXT"],
                    }
                )
                result.append(
                    {
                        "source": "Distributor Code",
                        "type": "lpg",
                        "value": item.get("distributor_details", {}).get(
                            "distributor_code"
                        ),
                        "showSource": True,
                        "category": RESPONSE_CATEGORIES["TEXT"],
                    }
                )
                result.append(
                    {
                        "source": "Distributor Name",
                        "type": "lpg",
                        "value": item.get("distributor_details", {}).get(
                            "distributor_name"
                        ),
                        "showSource": True,
                        "category": RESPONSE_CATEGORIES["TEXT"],
                    }
                )
                result.append(
                    {
                        "source": "Distributor Contact",
                        "type": "lpg",
                        "value": item.get("distributor_details", {}).get(
                            "distributor_contact"
                        ),
                        "showSource": True,
                        "category": RESPONSE_CATEGORIES["TEXT"],
                    }
                )
                result.append(
                    {
                        "source": "Distributor Address",
                        "type": "lpg",
                        "value": item.get("distributor_details", {}).get(
                            "distributor_address"
                        ),
                        "showSource": True,
                        "category": RESPONSE_CATEGORIES["TEXT"],
                    }
                )
            return result

    def _process_rc_response(self, data: dict) -> dict:
        """Process RC response"""
        final_data = {}
        for key, value in data.items():
            if not self._is_valid_value(value):
                data[key] = "Not Available"

            key_value = key.replace("_", " ").upper()

            if key in VEHICLE_INFO:
                final_data.setdefault("Vehicle Info", {})[key_value] = data[key]
            elif key in OWNER_INFO:
                final_data.setdefault("Owner Info", {})[key_value] = (
                    self._construct_address(data[key])
                    if key in ["split_permanent_address", "split_present_address"]
                    else data[key]
                )
            elif key in INSURANCE_INFO:
                final_data.setdefault("Insurance Info", {})[key_value] = data[key]

        return final_data

    def _process_challan_response(self, response: list) -> dict:
        """Process challan response"""
        formatted_response = []
        for challan in response:
            temp_results = {}
            for key, value in challan.items():
                if key in CHALLAN_LIST_INFO:
                    temp_results[key.replace("_", " ").upper()] = (
                        value if value is not None else "Not Available"
                    )
            formatted_response.append(temp_results)
        return {"Challan Info": formatted_response}

    def _process_fastatag_response(self, response: list) -> dict:
        """Process FastTag response"""
        formatted_response = []
        for fastatag in response:
            temp_results = {}
            for key, value in fastatag.items():
                if key in CHALLAN_LIST_INFO:
                    temp_results[key.replace("_", " ").upper()] = (
                        value if value is not None else "Not Available"
                    )
            formatted_response.append(temp_results)
        return {"Fast Tag Info": formatted_response}

    def _process_bank_search_response(self, data: dict) -> dict:
        """Process bank search response"""
        formatted_response = {}
        if "result" in data and data["result"]:
            result = data["result"]
            for key, value in result["details"].items():
                if isinstance(value, str):
                    formatted_response[key] = value
        else:
            formatted_response = {
                "Error": "Data Not Found for Given Bank Account and IFSC"
            }
        return formatted_response

    def _process_pan_response(self, data: dict) -> dict:
        """Process PAN response"""
        formatted_response = {}
        result = data.get("result", {})
        if "result" in data:
            for key, value in result.items():
                if isinstance(value, str):
                    formatted_response[key] = value
                elif key == "address" and isinstance(value, dict):
                    formatted_response["full_address"] = value.get("full", "")
                elif key == "din_info" and isinstance(value, dict):
                    company_list = value.get("company_list", [])
                    for index, company in enumerate(company_list):
                        for cl_key, cl_value in company.items():
                            formatted_response[f"{cl_key}_{index + 1}"] = cl_value
                    for din_key, din_value in value.items():
                        if din_key != "company_list":
                            formatted_response[din_key] = din_value
        else:
            formatted_response = {"Error": "Data Not Found for Given PAN"}

        return formatted_response

    def _process_license_data(self, data: dict) -> dict:
        """Process driving license data"""
        formatted_response = {}
        result = data.get("result", {})
        if result:
            for key, value in result.items():
                if isinstance(value, str) and key != "user_image":
                    formatted_response[key] = value
                elif key == "user_address":
                    for index, address in enumerate(value):
                        formatted_response[f"complete_address_{index + 1}"] = (
                            address.get("completeAddress", "Not Available")
                        )
                elif key == "vehicle_category_details":
                    for index, category in enumerate(value):
                        for k, v in category.items():
                            formatted_response[f"vehicle_category_{k}_{index + 1}"] = (
                                v if v is not None else "Not Available"
                            )
        else:
            formatted_response = {"Error": "Data Not Found for Given DL Number"}

        return formatted_response

    def _process_voter_id_data(self, data: dict) -> dict:
        """Process voter ID data"""
        formatted_response = {}
        result = data.get("result", {})
        if result:
            for key, value in result.items():
                if isinstance(value, str):
                    formatted_response[key] = value
                elif key == "address":
                    for add_key, add_value in value.items():
                        formatted_response[add_key] = add_value
                elif key == "polling_booth":
                    for poll_key, poll_value in value.items():
                        formatted_response[poll_key] = poll_value
        else:
            formatted_response = {"Error": "No Voter Id found for Given EPIC"}

        return formatted_response

    # Helper methods
    def _is_valid_value(self, value: Any) -> bool:
        """Check if value is valid"""
        return (
            value is not None
            and value != ""
            and (not isinstance(value, list) or len(value) > 0)
        )

    def _construct_address(self, data: dict) -> str:
        """Construct address from data"""
        fields = ["address_line", "city", "district", "state", "pincode", "country"]
        return ", ".join(
            filter(
                None,
                [self._get_first_non_empty_value(data.get(field)) for field in fields],
            )
        )

    def _get_first_non_empty_value(self, value: Any) -> str | None:
        """Get first non-empty value from list or return value"""
        if isinstance(value, list):
            return next((v for v in value if v), None)
        return value or None

    def _flatten_dict(
        self, d: MutableMapping, parent_key: str = "", sep: str = "."
    ) -> dict:
        """Flatten nested dictionary"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, MutableMapping):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _format_befisc_response(
        self, data: dict | list, func_name: str
    ) -> list[dict[str, Any]]:
        """Format Befisc response to standard format"""
        formatted_response = []

        # Handle list responses (like LPG)
        if isinstance(data, list):
            return data  # Already formatted

        # Handle dict responses
        if isinstance(data, dict):
            # Extract user info
            if "user_info" in data:
                user_info = data["user_info"]
                if user_info.get("name") and user_info["name"] != "Error":
                    formatted_response.append(
                        {
                            "source": "befisc",
                            "type": "name",
                            "value": user_info["name"],
                            "showSource": False,
                            "category": "TEXT",
                        }
                    )
                if user_info.get("email") and user_info["email"]:
                    formatted_response.append(
                        {
                            "source": "befisc",
                            "type": "email",
                            "value": user_info["email"],
                            "showSource": False,
                            "category": "TEXT",
                        }
                    )

            # Extract addresses
            if "address_list" in data:
                for address_item in data["address_list"]:
                    if (
                        address_item.get("address")
                        and address_item["address"] != "Error"
                    ):
                        address_str = address_item.get("address", "")
                        if address_item.get("city"):
                            address_str += f", {address_item['city']}"
                        if address_item.get("state"):
                            address_str += f", {address_item['state']}"
                        if address_item.get("pincode"):
                            address_str += f" - {address_item['pincode']}"

                        formatted_response.append(
                            {
                                "source": "befisc",
                                "type": "location",
                                "value": address_str,
                                "showSource": False,
                                "category": "TEXT",
                            }
                        )

            # Extract bank info
            if "bank_info" in data:
                bank_info = data["bank_info"]
                if bank_info:
                    for key, value in bank_info.items():
                        if value and value != "Error":
                            formatted_response.append(
                                {
                                    "source": "befisc",
                                    "type": "bank",
                                    "value": f"{key}: {value}",
                                    "showSource": False,
                                    "category": "TEXT",
                                }
                            )

            # For other structured data, add as raw
            if formatted_response:
                formatted_response.append(
                    {
                        "source": "befisc",
                        "type": "raw_data",
                        "value": str(data),
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        return formatted_response
