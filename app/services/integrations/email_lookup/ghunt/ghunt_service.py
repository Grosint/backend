from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from ghunt.apis.peoplepa import PeoplePaHttp

from app.core.exceptions import ExternalServiceException
from app.services.integrations.email_lookup.ghunt.calendar_service import (
    GHuntCalendarService,
)
from app.services.integrations.email_lookup.ghunt.credentials_manager import (
    GHuntCredentialsManager,
)
from app.services.integrations.email_lookup.ghunt.drive_service import GHuntDriveService
from app.services.integrations.email_lookup.ghunt.games_service import GHuntGamesService
from app.services.integrations.email_lookup.ghunt.geolocate_service import (
    GHuntGeolocateService,
)
from app.services.integrations.email_lookup.ghunt.maps_service import GHuntMapsService
from app.services.integrations.email_lookup.ghunt.people_service import (
    GHuntPeopleService,
)
from app.services.integrations.email_lookup.ghunt.vision_service import (
    GHuntVisionService,
)

logger = logging.getLogger(__name__)


class GHuntService:
    """
    Main GHunt service that aggregates all GHunt services.
    This is a blackbox service - takes an email and returns comprehensive results
    from all GHunt services (Email, People API, Maps, Play Games, Drive, etc.)
    """

    def __init__(self):
        self.name = "GHuntService"
        self._creds = None

        # Initialize all GHunt sub-services
        self.people_service = GHuntPeopleService()
        self.maps_service = GHuntMapsService()
        self.games_service = GHuntGamesService()
        self.drive_service = GHuntDriveService()
        self.vision_service = GHuntVisionService()
        self.calendar_service = GHuntCalendarService()
        self.geolocate_service = GHuntGeolocateService()

    def _get_credentials(self):
        """Get or load GHunt credentials"""
        if self._creds is None:
            try:
                self._creds = GHuntCredentialsManager.get_credentials()
            except ExternalServiceException:
                # Re-raise credential errors
                raise
            except Exception as e:
                logger.error(f"GHunt: Failed to load credentials: {e}")
                raise ExternalServiceException(
                    service_name="GHunt",
                    message=f"Failed to initialize GHunt credentials: {str(e)}",
                ) from e
        return self._creds

    def _get_people_api(self):
        """Get PeoplePaHttp API instance"""
        creds = self._get_credentials()
        return PeoplePaHttp(creds)

    async def search_email(self, email: str) -> dict[str, Any]:
        """
        Main entry point: Search email using all GHunt services.
        This is the blackbox method that orchestrates all GHunt services.

        Args:
            email: Email address to search for

        Returns:
            dict: Comprehensive results from all GHunt services
        """
        try:
            logger.info(f"GHunt: Starting comprehensive search for {email}")

            # Get credentials - handle errors gracefully
            try:
                self._get_credentials()
            except ExternalServiceException as e:
                logger.error(f"GHunt credentials error: {e.message}")
                return {
                    "found": False,
                    "source": "ghunt",
                    "data": None,
                    "confidence": 0.0,
                    "error": e.message,
                    "error_code": "CREDENTIALS_ERROR",
                    "_raw_response": {"error": e.message, "details": e.details},
                }

            # Step 1: Get basic email info and GAIA ID using PeoplePaHttp
            async with httpx.AsyncClient() as client:
                people_api = self._get_people_api()
                found, person = await people_api.people_lookup(
                    client, email, params_template="max_details"
                )
                if not found:
                    return {
                        "found": False,
                        "source": "ghunt",
                        "data": None,
                        "confidence": 0.0,
                        "_raw_response": {"error": "Person not found"},
                    }

                # Extract GAIA ID from person object
                gaia_id = getattr(person, "personId", None) or getattr(
                    person, "gaia_id", None
                )

                # Convert person object to dict for processing
                email_result = self._person_to_dict(person, email)

                # Format basic email data
                formatted_data = self._format_email_response(email_result, email)

                # Step 2: If we have GAIA ID, fetch additional data from other services
                additional_data = {}
                if gaia_id:
                    logger.info(
                        f"GHunt: Found GAIA ID {gaia_id}, fetching additional data"
                    )
                    additional_data = await self._fetch_additional_data(
                        client, email, gaia_id, email_result
                    )
                else:
                    logger.warning(
                        f"GHunt: No GAIA ID found for {email}, skipping additional services"
                    )

                # Combine all results
                if formatted_data or additional_data:
                    return {
                        "found": True,
                        "source": "ghunt",
                        "data": formatted_data,
                        "additional_data": additional_data,
                        "confidence": 0.9,
                        "_raw_response": {
                            "email_result": email_result,
                            "additional_data": additional_data,
                        },
                    }
                else:
                    return {
                        "found": False,
                        "source": "ghunt",
                        "data": None,
                        "confidence": 0.0,
                        "_raw_response": email_result,
                    }

        except ExternalServiceException:
            # Re-raise credential errors (already handled above)
            raise
        except Exception as e:
            logger.error(f"GHunt search failed: {e}")
            return {
                "found": False,
                "source": "ghunt",
                "error": str(e),
                "error_code": "SEARCH_ERROR",
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    async def _fetch_additional_data(
        self, client: httpx.AsyncClient, email: str, gaia_id: str, email_result: dict
    ) -> dict[str, Any]:
        """
        Fetch additional data from all GHunt services using GAIA ID.
        Runs all services in parallel for better performance.
        """
        additional_data = {}

        # Prepare tasks for parallel execution
        tasks = []

        # People API - get detailed person info
        tasks.append(("people", self.people_service.get_person_by_gaia_id(gaia_id)))

        # Maps - get reviews
        tasks.append(("maps", self.maps_service.get_maps_reviews(gaia_id)))

        # Play Games - try to get player profile (may not always work)
        # Note: Play Games uses player_id, not gaia_id directly
        # We'll skip this for now as it requires additional lookup

        # Vision - if profile photos exist, detect faces
        profile_photos = self._extract_profile_photos(email_result)
        if profile_photos:
            # Try to detect faces in the first profile photo
            tasks.append(
                ("vision", self.vision_service.detect_faces_from_url(profile_photos[0]))
            )

        # Execute all tasks in parallel
        results = await asyncio.gather(
            *[task for _, task in tasks], return_exceptions=True
        )

        # Process results
        for i, (name, _) in enumerate(tasks):
            result = results[i]
            if isinstance(result, Exception):
                logger.warning(f"GHunt {name} service failed: {result}")
                additional_data[name] = {"error": str(result)}
            else:
                additional_data[name] = result

        return additional_data

    def _extract_profile_photos(self, email_result: dict) -> list[str]:
        """Extract profile photo URLs from email result"""
        photos = []
        profile = email_result.get("profile") or email_result.get("person", {})
        if isinstance(profile, dict):
            profile_photos = profile.get("profilePhotos") or profile.get("photos", [])
            for photo in profile_photos:
                if isinstance(photo, dict):
                    photo_url = photo.get("url") or photo.get("photoUrl")
                else:
                    photo_url = str(photo)
                if photo_url:
                    photos.append(photo_url)
        return photos

    def _person_to_dict(self, person, email: str) -> dict[str, Any]:
        """Convert GHunt person object to dictionary with all available data"""
        result = {
            "email": email,
            "gaia_id": getattr(person, "personId", None)
            or getattr(person, "gaia_id", None),
        }

        # Extract profile information with all containers
        profile = {}

        # Extract names from all containers (PROFILE, CONTACT, etc.)
        if hasattr(person, "names") and person.names:
            profile["names"] = {}
            for container in person.names:
                name_obj = person.names[container]
                profile["names"][container] = {
                    "fullname": getattr(name_obj, "fullname", None),
                    "firstName": getattr(name_obj, "firstName", None),
                    "lastName": getattr(name_obj, "lastName", None),
                }

        # Extract emails from all containers
        if hasattr(person, "emails") and person.emails:
            profile["emails"] = {}
            for container in person.emails:
                email_obj = person.emails[container]
                profile["emails"][container] = {
                    "value": getattr(email_obj, "value", None),
                }

        # Extract profile photos from all containers
        if hasattr(person, "profilePhotos") and person.profilePhotos:
            profile["profilePhotos"] = {}
            for container in person.profilePhotos:
                photo_obj = person.profilePhotos[container]
                profile["profilePhotos"][container] = {
                    "url": getattr(photo_obj, "url", None),
                    "isDefault": getattr(photo_obj, "isDefault", False),
                }

        # Extract phones from all containers
        if hasattr(person, "phones") and person.phones:
            profile["phones"] = {}
            for container in person.phones:
                phone_obj = person.phones[container]
                profile["phones"][container] = {
                    "value": getattr(phone_obj, "value", None),
                }

        # Extract personId for Maps profile link
        if hasattr(person, "personId") and person.personId:
            profile["personId"] = person.personId

        # Extract inAppReachability (activated Google services)
        if hasattr(person, "inAppReachability") and person.inAppReachability:
            profile["inAppReachability"] = {}
            for container in person.inAppReachability:
                reachability_obj = person.inAppReachability[container]
                if hasattr(reachability_obj, "apps"):
                    profile["inAppReachability"][container] = {
                        "apps": (
                            list(reachability_obj.apps) if reachability_obj.apps else []
                        ),
                    }

        result["profile"] = profile
        return result

    def _format_email_response(
        self, result: dict[str, Any] | None, email: str
    ) -> list[dict]:
        """Format GHunt email response to standard format following coding standards"""
        formatted_response = []

        if not result:
            return formatted_response

        data = result

        # Extract names from PROFILE container
        if (
            "profile" in data
            and "names" in data["profile"]
            and "PROFILE" in data["profile"]["names"]
        ):
            profile_names = data["profile"]["names"]["PROFILE"]
            if profile_names.get("fullname"):
                formatted_response.append(
                    {
                        "type": "name",
                        "source": "profile",
                        "value": profile_names["fullname"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
            elif profile_names.get("firstName") and profile_names.get("lastName"):
                formatted_response.append(
                    {
                        "type": "name",
                        "source": "profile",
                        "value": profile_names["firstName"]
                        + " "
                        + profile_names["lastName"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
            elif profile_names.get("firstName"):
                formatted_response.append(
                    {
                        "type": "name",
                        "source": "profile",
                        "value": profile_names["firstName"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
            elif profile_names.get("lastName"):
                formatted_response.append(
                    {
                        "type": "name",
                        "source": "profile",
                        "value": profile_names["lastName"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        # Extract names from CONTACT container
        if (
            "profile" in data
            and "names" in data["profile"]
            and "CONTACT" in data["profile"]["names"]
        ):
            contact_names = data["profile"]["names"]["CONTACT"]
            if contact_names.get("fullname"):
                formatted_response.append(
                    {
                        "type": "name",
                        "source": "contact",
                        "value": contact_names["fullname"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
            elif contact_names.get("firstName") and contact_names.get("lastName"):
                formatted_response.append(
                    {
                        "type": "name",
                        "source": "contact",
                        "value": contact_names["firstName"]
                        + " "
                        + contact_names["lastName"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
            elif contact_names.get("firstName"):
                formatted_response.append(
                    {
                        "type": "name",
                        "source": "contact",
                        "value": contact_names["firstName"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
            elif contact_names.get("lastName"):
                formatted_response.append(
                    {
                        "type": "name",
                        "source": "contact",
                        "value": contact_names["lastName"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        # Extract emails from CONTACT container
        if (
            "profile" in data
            and "emails" in data["profile"]
            and "CONTACT" in data["profile"]["emails"]
        ):
            contact_email = data["profile"]["emails"]["CONTACT"].get("value")
            if contact_email:
                formatted_response.append(
                    {
                        "type": "email",
                        "source": "contact",
                        "value": contact_email,
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        # Extract emails from PROFILE container
        if (
            "profile" in data
            and "emails" in data["profile"]
            and "PROFILE" in data["profile"]["emails"]
        ):
            profile_email = data["profile"]["emails"]["PROFILE"].get("value")
            if profile_email:
                formatted_response.append(
                    {
                        "type": "email",
                        "source": "profile",
                        "value": profile_email,
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        # Extract profile photos from PROFILE container
        if (
            "profile" in data
            and "profilePhotos" in data["profile"]
            and "PROFILE" in data["profile"]["profilePhotos"]
        ):
            profile_photo = data["profile"]["profilePhotos"]["PROFILE"]
            photo_url = profile_photo.get("url")
            if photo_url:
                formatted_response.append(
                    {
                        "type": "image",
                        "source": "profile",
                        "showSource": False,
                        "value": photo_url,
                        "category": "IMAGE",
                    }
                )

        # Extract Maps profile link using personId
        if "profile" in data and "personId" in data["profile"]:
            person_id = data["profile"]["personId"]
            if person_id:
                formatted_response.append(
                    {
                        "type": "mapsProfile",
                        "source": "maps",
                        "value": f"https://www.google.com/maps/contrib/{person_id}/reviews",
                        "showSource": False,
                        "category": "LINK",
                    }
                )

        # Extract inAppReachability (activated Google services)
        if (
            "profile" in data
            and "inAppReachability" in data["profile"]
            and "PROFILE" in data["profile"]["inAppReachability"]
            and "apps" in data["profile"]["inAppReachability"]["PROFILE"]
        ):
            apps = data["profile"]["inAppReachability"]["PROFILE"]["apps"]
            if apps:
                for app in apps:
                    formatted_response.append(
                        {
                            "type": "otherApps",
                            "source": None,
                            "value": app,
                            "showSource": False,
                            "category": "TEXT",
                        }
                    )
            else:
                formatted_response.append(
                    {
                        "type": "otherApps",
                        "source": None,
                        "value": None,
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
        else:
            formatted_response.append(
                {
                    "type": "otherApps",
                    "source": None,
                    "value": None,
                    "showSource": False,
                    "category": "TEXT",
                }
            )

        return formatted_response
