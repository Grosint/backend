from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from ghunt.apis.vision import VisionHttp

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
            creds = self._get_credentials()
            vision_api = VisionHttp(creds)

            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                if response.status_code != 200:
                    return {"success": False, "error": "Failed to download image"}

                image_b64 = base64.b64encode(response.content).decode()

                try:
                    rate_limited, faces_found, faces_result = (
                        await vision_api.detect_faces(client, image_content=image_b64)
                    )
                except KeyError as ke:
                    logger.warning(
                        f"GHunt Vision API returned unexpected response: missing key {ke}"
                    )
                    return {
                        "success": False,
                        "error": f"Vision API returned unexpected response (missing key: {ke})",
                    }

                if rate_limited:
                    return {"success": False, "error": "Vision API rate limited"}

                if not faces_found:
                    return {"success": False, "error": "No faces detected"}

                faces = []
                for face in faces_result.face_annotations:
                    faces.append(
                        {
                            "detection_confidence": getattr(
                                face, "detection_confidence", None
                            ),
                            "joy": getattr(face, "joy_likelihood", None),
                            "sorrow": getattr(face, "sorrow_likelihood", None),
                            "anger": getattr(face, "anger_likelihood", None),
                            "surprise": getattr(face, "surprise_likelihood", None),
                            "headwear": getattr(face, "headwear_likelihood", None),
                        }
                    )

                return {
                    "success": True,
                    "faces_count": len(faces),
                    "faces": faces,
                }
        except Exception as e:
            logger.error(f"GHunt Vision API error: {e}")
            return {"success": False, "error": str(e)}

    async def detect_faces_from_base64(self, image_b64: str) -> dict[str, Any]:
        """Detect faces in a base64 encoded image"""
        try:
            creds = self._get_credentials()
            vision_api = VisionHttp(creds)

            async with httpx.AsyncClient() as client:
                rate_limited, faces_found, faces_result = await vision_api.detect_faces(
                    client, image_content=image_b64
                )

                if rate_limited:
                    return {"success": False, "error": "Vision API rate limited"}

                if not faces_found:
                    return {"success": False, "error": "No faces detected"}

                faces = []
                for face in faces_result.face_annotations:
                    faces.append(
                        {
                            "detection_confidence": getattr(
                                face, "detection_confidence", None
                            ),
                            "joy": getattr(face, "joy_likelihood", None),
                            "sorrow": getattr(face, "sorrow_likelihood", None),
                            "anger": getattr(face, "anger_likelihood", None),
                            "surprise": getattr(face, "surprise_likelihood", None),
                            "headwear": getattr(face, "headwear_likelihood", None),
                        }
                    )

                return {
                    "success": True,
                    "faces_count": len(faces),
                    "faces": faces,
                }
        except Exception as e:
            logger.error(f"GHunt Vision API error: {e}")
            return {"success": False, "error": str(e)}
