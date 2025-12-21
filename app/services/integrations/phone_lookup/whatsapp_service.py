from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for WhatsApp API integration"""

    def __init__(self):
        self.name = "WhatsAppService"
        self.client = ResilientHttpClient()

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using WhatsApp API"""
        try:
            logger.info(f"WhatsApp: Searching {country_code}{phone}")

            country_code_clean = country_code.replace("+", "")
            url = f"https://whatsapp-data1.p.rapidapi.com/number/{country_code_clean}{phone}"

            response = await self.client.request(
                "GET",
                url,
                headers={
                    "x-rapidapi-key": settings.RAPIDAPI_KEY,
                    "x-rapidapi-host": "whatsapp-data1.p.rapidapi.com",
                },
                circuit_key="whatsapp_api",
            )

            data = response.json()
            raw_response = data  # Store raw response before processing

            if "error" in data or "data" not in data:
                return {
                    "found": False,
                    "source": "whatsapp",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": raw_response,
                }
            else:
                # Format WhatsApp response
                formatted_data = self._format_response(data)
                return {
                    "found": True,
                    "source": "whatsapp",
                    "data": formatted_data,
                    "confidence": 0.9,
                    "_raw_response": raw_response,
                }
        except Exception as e:
            logger.error(f"WhatsApp search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "error": str(e),
                "_raw_response": raw_response,
            }

    def _format_response(self, data: dict) -> list[dict]:
        """Format WhatsApp response to standard format"""
        formatted_response = []

        # Account exists indicator
        formatted_response.append(
            {
                "source": "Account Exist",
                "type": "whatsapp",
                "value": "Yes",
                "showSource": True,
                "category": "TEXT",
            }
        )

        # Extract phone number (prefer formatted phone, fallback to number)
        phone = data.get("phone") or data.get("number")
        if phone:
            formatted_response.append(
                {
                    "source": "Phone Number",
                    "type": "whatsapp",
                    "value": phone,
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract country code
        country_code = data.get("countryCode")
        if country_code:
            formatted_response.append(
                {
                    "source": "Country Code",
                    "type": "whatsapp",
                    "value": country_code,
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract about text (only if it exists and is not empty)
        about = data.get("about")
        if about:
            formatted_response.append(
                {
                    "source": "About",
                    "type": "whatsapp",
                    "value": about,
                    "showSource": True,
                    "category": "TEXT",
                }
            )

        # Extract profile picture (only if available and authorized)
        profile_pic = data.get("profilePic")
        image_status = data.get("image_status")
        if profile_pic and image_status != "not-authorized":
            formatted_response.append(
                {
                    "source": "whatsapp",
                    "type": "image",
                    "value": profile_pic,
                    "showSource": False,
                    "category": "IMAGE",
                }
            )

        # Extract verification status
        is_verified = data.get("isVerified", False)
        formatted_response.append(
            {
                "source": "Verified",
                "type": "whatsapp",
                "value": "Yes" if is_verified else "No",
                "showSource": True,
                "category": "TEXT",
            }
        )

        # Business account specific fields
        if data.get("isBusiness", False):
            # Extract business profile information
            if "businessProfile" in data:
                business_profile = data["businessProfile"]

                # Extract business address
                address = business_profile.get("address")
                if address:
                    formatted_response.append(
                        {
                            "source": "Address",
                            "type": "whatsapp",
                            "value": address,
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

                # Extract business description
                description = business_profile.get("description")
                if description:
                    formatted_response.append(
                        {
                            "source": "Description",
                            "type": "whatsapp",
                            "value": description,
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

                # Extract business email
                email = business_profile.get("email")
                if email:
                    formatted_response.append(
                        {
                            "source": "Email",
                            "type": "whatsapp",
                            "value": email,
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

            # Extract enterprise status
            is_enterprise = data.get("isEnterprise", False)
            if is_enterprise:
                formatted_response.append(
                    {
                        "source": "Enterprise Account",
                        "type": "whatsapp",
                        "value": "Yes",
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

        return formatted_response
