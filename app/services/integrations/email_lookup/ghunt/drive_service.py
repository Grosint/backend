from __future__ import annotations

import logging
from typing import Any

import httpx
from ghunt.apis.drive import DriveHttp

from app.services.integrations.email_lookup.ghunt.credentials_manager import (
    GHuntCredentialsManager,
)

logger = logging.getLogger(__name__)


class GHuntDriveService:
    """Service for GHunt Google Drive integration"""

    def __init__(self):
        self.name = "GHuntDriveService"
        self._creds = None
        self._drive_api = None

    def _get_credentials(self):
        """Get GHunt credentials"""
        if self._creds is None:
            self._creds = GHuntCredentialsManager.get_credentials()
        return self._creds

    def _get_drive_api(self):
        """Get Drive API instance"""
        if self._drive_api is None:
            creds = self._get_credentials()
            self._drive_api = DriveHttp(creds)
        return self._drive_api

    async def get_file_info(self, file_id: str) -> dict[str, Any]:
        """Get information about a Google Drive file"""
        try:
            drive_api = self._get_drive_api()

            async with httpx.AsyncClient() as client:
                file_info = await drive_api.get_file_metadata(client, file_id)

                if not file_info:
                    return {"found": False, "error": "File not found"}

                return {
                    "found": True,
                    "file_id": file_info.get("id"),
                    "name": file_info.get("name"),
                    "mime_type": file_info.get("mimeType"),
                    "size": file_info.get("size"),
                    "created_time": file_info.get("createdTime"),
                    "modified_time": file_info.get("modifiedTime"),
                    "owners": [
                        {
                            "display_name": owner.get("displayName"),
                            "email": owner.get("emailAddress"),
                            "photo_link": owner.get("photoLink"),
                        }
                        for owner in file_info.get("owners", [])
                    ],
                    "sharing_user": file_info.get("sharingUser"),
                    "permissions": file_info.get("permissions", []),
                }
        except Exception as e:
            logger.error(f"GHunt Drive API error: {e}")
            return {"found": False, "error": str(e)}
