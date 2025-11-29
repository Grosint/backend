from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from ghunt.helpers.ia import detect_face

from app.services.integrations.email_lookup.ghunt.credentials_manager import (
    GHuntCredentialsManager,
)

logger = logging.getLogger(__name__)


class GHuntVisionService:
    """Service for GHunt Vision API integration"""

    def __init__(self):
        self.name = "GHuntVisionService"
        self._creds = None

    def _get_credentials(self):
        """Get GHunt credentials"""
        if self._creds is None:
            self._creds = GHuntCredentialsManager.get_credentials()
        return self._creds

    async def detect_faces_from_url(self, image_url: str) -> dict[str, Any]:
        """Detect faces in an image from URL"""
        try:
            async with httpx.AsyncClient() as client:
                # Download image
                response = await client.get(image_url)
                if response.status_code != 200:
                    return {"success": False, "error": "Failed to download image"}

                # Convert to base64
                image_b64 = base64.b64encode(response.content).decode()

                # Detect faces
                result = await detect_face(client, image_b64)

                if not result or not result.get("success"):
                    return {"success": False, "error": "No faces detected"}

                return {
                    "success": True,
                    "faces_count": len(result.get("faces", [])),
                    "faces": result.get("faces", []),
                }
        except Exception as e:
            logger.error(f"GHunt Vision API error: {e}")
            return {"success": False, "error": str(e)}

    async def detect_faces_from_base64(self, image_b64: str) -> dict[str, Any]:
        """Detect faces in a base64 encoded image"""
        try:
            async with httpx.AsyncClient() as client:
                result = await detect_face(client, image_b64)

                if not result or not result.get("success"):
                    return {"success": False, "error": "No faces detected"}

                return {
                    "success": True,
                    "faces_count": len(result.get("faces", [])),
                    "faces": result.get("faces", []),
                }
        except Exception as e:
            logger.error(f"GHunt Vision API error: {e}")
            return {"success": False, "error": str(e)}
