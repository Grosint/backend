from __future__ import annotations

import logging
from typing import Any

import httpx
from ghunt.apis.peoplepa import PeoplePaHttp

from app.services.integrations.email_lookup.ghunt.credentials_manager import (
    GHuntCredentialsManager,
)

logger = logging.getLogger(__name__)


class GHuntPeopleService:
    """Service for GHunt People API integration"""

    def __init__(self):
        self.name = "GHuntPeopleService"
        self._creds = None

    def _get_credentials(self):
        """Get GHunt credentials"""
        if self._creds is None:
            self._creds = GHuntCredentialsManager.get_credentials()
        return self._creds

    async def get_person_by_email(self, email: str) -> dict[str, Any]:
        """Get person information by email"""
        try:
            creds = self._get_credentials()
            people_api = PeoplePaHttp(creds)

            async with httpx.AsyncClient() as client:
                found, person = await people_api.people_lookup(
                    client, email, params_template="max_details"
                )

                if not found:
                    return {"found": False, "error": "Person not found"}

                result = {"found": True}

                # Extract information based on what's available
                if hasattr(person, "gaia_id") and person.gaia_id:
                    result["gaia_id"] = person.gaia_id

                if hasattr(person, "names") and person.names:
                    if "PROFILE" in person.names:
                        result["name"] = person.names["PROFILE"].fullname
                    elif "CONTACT" in person.names:
                        result["name"] = person.names["CONTACT"].fullname
                        result["note"] = "Name from contacts only"

                if hasattr(person, "emails") and person.emails:
                    result["emails"] = [email.value for email in person.emails]

                if hasattr(person, "phones") and person.phones:
                    result["phones"] = [phone.value for phone in person.phones]

                if hasattr(person, "profilePhotos") and person.profilePhotos:
                    result["profile_photos"] = [
                        photo.url for photo in person.profilePhotos
                    ]

                return result
        except Exception as e:
            logger.error(f"GHunt People API error: {e}")
            return {"found": False, "error": str(e)}

    async def get_person_by_gaia_id(self, gaia_id: str) -> dict[str, Any]:
        """Get person information by GAIA ID"""
        try:
            creds = self._get_credentials()
            people_api = PeoplePaHttp(creds)

            async with httpx.AsyncClient() as client:
                found, person = await people_api.people_gaia_id_lookup(
                    client, gaia_id, params_template="max_details"
                )

                if not found:
                    return {"found": False, "error": "Person not found"}

                result = {"found": True}

                if hasattr(person, "gaia_id") and person.gaia_id:
                    result["gaia_id"] = person.gaia_id

                if hasattr(person, "names") and person.names:
                    if "PROFILE" in person.names:
                        result["name"] = person.names["PROFILE"].fullname
                    elif "CONTACT" in person.names:
                        result["name"] = person.names["CONTACT"].fullname

                if hasattr(person, "emails") and person.emails:
                    result["emails"] = [email.value for email in person.emails]

                if hasattr(person, "phones") and person.phones:
                    result["phones"] = [phone.value for phone in person.phones]

                if hasattr(person, "profilePhotos") and person.profilePhotos:
                    result["profile_photos"] = [
                        photo.url for photo in person.profilePhotos
                    ]

                return result
        except Exception as e:
            logger.error(f"GHunt People API error: {e}")
            return {"found": False, "error": str(e)}
