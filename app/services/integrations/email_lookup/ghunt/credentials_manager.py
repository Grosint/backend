from __future__ import annotations

import logging
from pathlib import Path

from ghunt.objects.base import GHuntCreds

from app.core.exceptions import ExternalServiceException
from app.utils.path_utils import get_project_root

logger = logging.getLogger(__name__)


class GHuntCredentialsManager:
    """Manager for GHunt credentials loading and validation"""

    _instance: GHuntCreds | None = None
    _creds_path: Path | None = None

    @classmethod
    def get_credentials_path(cls) -> Path:
        """Get the path to GHunt credentials file"""
        if cls._creds_path is None:
            # GHunt credentials path: project_root/.ghunt/.malfrats/creds.m
            # Get project root directory using standard utility function
            project_root = get_project_root()
            cls._creds_path = project_root / ".ghunt" / ".malfrats" / "creds.m"
        return cls._creds_path

    @classmethod
    def load_credentials(cls) -> GHuntCreds:
        """Load GHunt credentials from file"""
        creds_path = cls.get_credentials_path()

        if not creds_path.exists():
            raise ExternalServiceException(
                service_name="GHunt",
                message=f"GHunt credentials not found at {creds_path}. Please run 'ghunt login' to authenticate.",
                details={"creds_path": str(creds_path)},
            )

        try:
            # Pass the project-based creds path to GHuntCreds
            creds = GHuntCreds(creds_path=str(creds_path))
            # GHunt's load_creds() method loads from the creds_path specified in __init__
            creds.load_creds()

            # Validate credentials are loaded by checking if cookies exist
            if not hasattr(creds, "cookies") or not creds.cookies:
                raise ExternalServiceException(
                    service_name="GHunt",
                    message="GHunt credentials are invalid or expired. Please run 'ghunt login' to re-authenticate.",
                    details={"creds_path": str(creds_path)},
                )

            # Additional validation: check if cookies dict is not empty
            if isinstance(creds.cookies, dict) and len(creds.cookies) == 0:
                raise ExternalServiceException(
                    service_name="GHunt",
                    message="GHunt credentials are invalid or expired. Please run 'ghunt login' to re-authenticate.",
                    details={"creds_path": str(creds_path)},
                )

            return creds
        except FileNotFoundError:
            raise ExternalServiceException(
                service_name="GHunt",
                message=f"GHunt credentials not found at {creds_path}. Please run 'ghunt login' to authenticate.",
                details={"creds_path": str(creds_path)},
            ) from None
        except Exception as e:
            if isinstance(e, ExternalServiceException):
                raise
            # Check if it's a credential-related error
            error_str = str(e).lower()
            if (
                "credential" in error_str
                or "cookie" in error_str
                or "auth" in error_str
            ):
                raise ExternalServiceException(
                    service_name="GHunt",
                    message="GHunt credentials are invalid or expired. Please run 'ghunt login' to re-authenticate.",
                    details={"creds_path": str(creds_path), "error": str(e)},
                ) from e
            raise ExternalServiceException(
                service_name="GHunt",
                message=f"Failed to load GHunt credentials: {str(e)}",
                details={"creds_path": str(creds_path), "error": str(e)},
            ) from e

    @classmethod
    def get_credentials(cls) -> GHuntCreds:
        """Get GHunt credentials (singleton pattern)"""
        if cls._instance is None:
            cls._instance = cls.load_credentials()
        return cls._instance

    @classmethod
    def reload_credentials(cls):
        """Reload credentials (useful if credentials are updated)"""
        cls._instance = None
        cls._instance = cls.load_credentials()
