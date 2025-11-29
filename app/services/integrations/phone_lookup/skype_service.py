from __future__ import annotations

import asyncio
import logging
import os
import random
from pathlib import Path
from typing import Any

from skpy import Skype

from app.core.config import settings
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class SkypeService:
    """Service for Skype API integration"""

    def __init__(self):
        self.name = "SkypeService"
        self.client = ResilientHttpClient()
        # Store token file in project root
        self.token_file = (
            Path(__file__).parent.parent.parent.parent / "skype_tokens.txt"
        )
        self._skype_token: str | None = None

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """
        Search phone number using Skype API.
        Note: Skype searches by email, so this method extracts emails from phone lookup
        results and searches Skype. If no email is provided, returns not found.
        """
        try:
            logger.info(f"Skype: Searching {country_code}{phone}")

            # Note: Skype API searches by email/username, not phone directly
            # This service is designed to be called with email extracted from other phone lookup results
            # For direct phone lookup, we return not found
            return {
                "found": False,
                "source": "skype",
                "data": None,
                "confidence": 0.0,
                "error": "Skype search requires email address, not phone number",
                "_raw_response": None,
            }

        except Exception as e:
            logger.error(f"Skype search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "error": str(e),
                "_raw_response": raw_response,
            }

    async def search_email(self, email: str) -> dict[str, Any]:
        """
        Search Skype profiles by email address.

        Args:
            email: Email address to search for

        Returns:
            dict: Skype search results
        """
        try:
            logger.info(f"Skype: Searching email {email}")

            # Get or generate Skype token
            token = await self._get_skype_token()
            if not token:
                return {
                    "found": False,
                    "source": "skype",
                    "data": None,
                    "confidence": 0.0,
                    "error": "Failed to obtain Skype authentication token",
                    "_raw_response": None,
                }

            # Perform search using Skype API
            search_results = await self._search_skype(email, token)

            if not search_results or len(search_results) == 0:
                return {
                    "found": False,
                    "source": "skype",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": {"results": []},
                }

            # Format response
            formatted_data = self._format_response(search_results)
            return {
                "found": True,
                "source": "skype",
                "data": formatted_data,
                "confidence": 0.8,
                "_raw_response": {"results": search_results},
            }

        except Exception as e:
            logger.error(f"Skype email search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            return {
                "found": False,
                "error": str(e),
                "_raw_response": raw_response,
            }

    async def _get_skype_token(self) -> str | None:
        """Get or generate Skype authentication token"""
        try:
            # Try to read existing token
            if self.token_file.exists() and self._skype_token:
                return self._skype_token

            # Run token generation in thread pool (skpy is synchronous)
            token = await asyncio.to_thread(self._generate_skype_token)
            if token:
                self._skype_token = token
            return token

        except Exception as e:
            logger.error(f"Failed to get Skype token: {e}")
            return None

    def _generate_skype_token(self) -> str | None:
        """Generate Skype authentication token (synchronous)"""
        try:
            sk = None

            # Try to read existing token file
            if self.token_file.exists():
                sk = Skype(connect=False)
                sk.conn.tokenFile = str(self.token_file)
                try:
                    sk.conn.readToken()
                    if sk.conn.tokens and sk.conn.tokens.get("skype"):
                        logger.info("Loaded existing Skype token")
                        return sk.conn.tokens["skype"]
                except Exception as e:
                    logger.warning(f"Failed to read existing token: {e}")

            # Generate new token
            if not sk or not sk.conn.tokens or not sk.conn.tokens.get("skype"):
                # Get Skype credentials from config
                skype_users = self._get_skype_users()
                if not skype_users:
                    logger.error("No Skype users configured")
                    return None

                # Remove old token file if exists
                if self.token_file.exists():
                    os.remove(self.token_file)

                # Try each user until one works
                for user_email, password in skype_users:
                    try:
                        logger.info(f"Attempting to authenticate with {user_email}")
                        sk = Skype(user_email, password, str(self.token_file))
                        if sk and sk.conn.tokens and sk.conn.tokens.get("skype"):
                            logger.info(f"Successfully authenticated with {user_email}")
                            return sk.conn.tokens["skype"]
                    except Exception as e:
                        logger.warning(f"Failed to authenticate with {user_email}: {e}")
                        continue

            return None

        except Exception as e:
            logger.error(f"Token generation failed: {e}")
            return None

    def _get_skype_users(self) -> list[tuple[str, str]]:
        """Get Skype user credentials from config"""
        users = []
        # Check for configured Skype users (similar to Telegram pattern)
        # Format: SKYPE_USER_1, SKYPE_PASSWORD_1, etc.
        max_users = getattr(settings, "SKYPE_MAX_ACCOUNTS", 3)
        for i in range(1, max_users + 1):
            user_key = f"SKYPE_USER_{i}"
            password_key = f"SKYPE_PASSWORD_{i}"
            user = getattr(settings, user_key, None)
            password = getattr(settings, password_key, None)
            if user and password:
                users.append((user, password))
        return users

    async def _search_skype(
        self, search_query: str, token: str
    ) -> list[dict[str, Any]]:
        """Search Skype using the API (synchronous skpy call wrapped in async)"""
        try:
            # Run synchronous search in thread pool
            results = await asyncio.to_thread(
                self._search_skype_sync, search_query, token
            )
            return results
        except Exception as e:
            logger.error(f"Skype search execution failed: {e}")
            return []

    def _search_skype_sync(self, search_query: str, token: str) -> list[dict[str, Any]]:
        """Synchronous Skype search implementation"""
        import requests

        session = requests.Session()
        session.headers.update(
            {
                "X-Skypetoken": token,
                "X-ECS-ETag": "Fzn/9gnnfHwbTYyoLcWa1FhbSVkgRg28SzNJqolgQHg=",
                "X-Skype-Client": "1419/8.26.0.70",
                "X-SkypeGraphServiceSettings": '{"experiment":"MinimumFriendsForAnnotationsEnabled","geoProximity":"disabled","minimumFriendsForAnnotationsEnabled":"true","minimumFriendsForAnnotations":2,"demotionScoreEnabled":"true"}',
                "accept-encoding": "gzip",
                "user-agent": "okhttp/3.10.0",
            }
        )

        params = {
            "searchString": search_query,
            "requestId": random.randint(int(1e13), int(9e13)),  # nosec B311
        }

        try:
            search_response = session.get(
                "https://skypegraph.skype.com/v2.0/search", params=params, timeout=30
            )

            if search_response.status_code == 200:
                json_response = search_response.json()
                relevant_data = json_response.get("results", [])
                output = []
                for info in relevant_data:
                    if "nodeProfileData" in info:
                        output.append(info["nodeProfileData"])
                return output
            else:
                logger.warning(
                    f"Skype API returned status {search_response.status_code}"
                )
                return []

        except Exception as e:
            logger.error(f"Skype API request failed: {e}")
            raise

    def _format_response(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format Skype response to standard format"""
        formatted_response = []

        for result in results:
            # Extract profile information
            if "displayName" in result:
                formatted_response.append(
                    {
                        "source": "skype",
                        "type": "name",
                        "value": result["displayName"],
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

            if "mri" in result:
                formatted_response.append(
                    {
                        "source": "Skype ID",
                        "type": "skype_id",
                        "value": result["mri"],
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            if "avatarUrl" in result:
                formatted_response.append(
                    {
                        "source": "skype",
                        "type": "image",
                        "value": result["avatarUrl"],
                        "showSource": False,
                        "category": "IMAGE",
                    }
                )

            if "location" in result:
                formatted_response.append(
                    {
                        "source": "Location",
                        "type": "location",
                        "value": result["location"],
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

            if "about" in result:
                formatted_response.append(
                    {
                        "source": "About",
                        "type": "about",
                        "value": result["about"],
                        "showSource": True,
                        "category": "TEXT",
                    }
                )

        return formatted_response
