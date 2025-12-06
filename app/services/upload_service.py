"""Service for handling file uploads."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.adapters.azure_blob_adapter import AzureBlobAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


class UploadService:
    """Service for managing file uploads."""

    def __init__(self):
        """Initialize the upload service."""
        self.blob_adapter = AzureBlobAdapter()
        self.max_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        self.allowed_extensions = [
            ext.strip().lower() for ext in settings.ALLOWED_FILE_EXTENSIONS.split(",")
        ]

    def _validate_file(
        self, filename: str, file_size: int | None = None
    ) -> tuple[bool, str | None]:
        """
        Validate file name and size.

        Args:
            filename: Name of the file
            file_size: Size of the file in bytes (optional)

        Returns:
            tuple: (is_valid, error_message)
        """
        # Check file extension
        file_ext = Path(filename).suffix.lower().lstrip(".")
        if file_ext not in self.allowed_extensions:
            return (
                False,
                f"File extension '{file_ext}' not allowed. "
                f"Allowed extensions: {', '.join(self.allowed_extensions)}",
            )

        # Check file size if provided
        if file_size is not None and file_size > self.max_size_bytes:
            max_size_mb = settings.MAX_UPLOAD_SIZE_MB
            return (
                False,
                f"File size exceeds maximum allowed size of {max_size_mb} MB",
            )

        return (True, None)

    def _generate_blob_name(
        self, filename: str, folder: str | None = None, prefix: str | None = None
    ) -> str:
        """
        Generate a unique blob name based on folder structure.

        Args:
            filename: Original filename
            folder: Optional folder path (e.g., "images", "documents/user123")
            prefix: Optional prefix (e.g., timestamp, user ID)

        Returns:
            str: Generated blob name/path
        """
        # Get file extension
        file_ext = Path(filename).suffix
        base_name = Path(filename).stem

        # Generate unique identifier
        unique_id = str(uuid.uuid4())[:8]

        # Build the path
        path_parts = []

        # Add folder if provided
        if folder:
            # Normalize folder path (remove leading/trailing slashes)
            folder = folder.strip("/")
            if folder:
                path_parts.append(folder)

        # Add prefix if provided
        if prefix:
            path_parts.append(prefix)

        # Add timestamp for organization
        timestamp = datetime.utcnow().strftime("%Y/%m/%d")
        path_parts.append(timestamp)

        # Add unique filename
        safe_filename = f"{base_name}_{unique_id}{file_ext}"
        path_parts.append(safe_filename)

        return "/".join(path_parts)

    async def upload_file_direct(
        self,
        file_content: bytes,
        filename: str,
        folder: str | None = None,
        prefix: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file directly through the backend.

        Args:
            file_content: File content as bytes
            filename: Original filename
            folder: Optional folder path for organization
            prefix: Optional prefix (e.g., user ID, category)
            metadata: Optional metadata to attach

        Returns:
            dict: Upload result with URL and metadata
        """
        # Validate file
        is_valid, error_msg = self._validate_file(filename, len(file_content))
        if not is_valid:
            raise ValueError(error_msg)

        # Generate blob name
        blob_name = self._generate_blob_name(filename, folder, prefix)

        # Prepare metadata
        upload_metadata = {
            "original_filename": filename,
            "uploaded_at": datetime.utcnow().isoformat(),
            "upload_method": "direct",
        }
        if metadata:
            upload_metadata.update(metadata)

        # Upload to Azure
        result = await self.blob_adapter.upload_file(
            file_content=file_content,
            blob_name=blob_name,
            metadata=upload_metadata,
        )

        # Add additional information
        result["original_filename"] = filename
        result["folder"] = folder
        result["prefix"] = prefix

        logger.info(f"Direct upload completed: {blob_name}")
        return result

    async def generate_presigned_url(
        self,
        filename: str,
        folder: str | None = None,
        prefix: str | None = None,
        expiry_minutes: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a pre-signed URL for client-side upload.

        Args:
            filename: Original filename
            folder: Optional folder path for organization
            prefix: Optional prefix (e.g., user ID, category)
            expiry_minutes: URL expiration time in minutes
            metadata: Optional metadata to attach

        Returns:
            dict: Pre-signed URL and upload information
        """
        # Validate file (without size check since we don't have it yet)
        is_valid, error_msg = self._validate_file(filename)
        if not is_valid:
            raise ValueError(error_msg)

        # Generate blob name
        blob_name = self._generate_blob_name(filename, folder, prefix)

        # Prepare metadata
        upload_metadata = {
            "original_filename": filename,
            "upload_method": "presigned_url",
        }
        if metadata:
            upload_metadata.update(metadata)

        # Generate pre-signed URL
        result = await self.blob_adapter.generate_presigned_url(
            blob_name=blob_name,
            expiry_minutes=expiry_minutes,
            metadata=upload_metadata,
        )

        # Add additional information
        result["original_filename"] = filename
        result["folder"] = folder
        result["prefix"] = prefix

        logger.info(f"Pre-signed URL generated: {blob_name}")
        return result

    async def delete_file(self, blob_name: str) -> bool:
        """
        Delete a file from storage.

        Args:
            blob_name: Name/path of the blob to delete

        Returns:
            bool: True if deleted successfully
        """
        return await self.blob_adapter.delete_file(blob_name)

    async def get_file_url(self, blob_name: str, generate_sas: bool = False) -> str:
        """
        Get the URL for a file.

        Args:
            blob_name: Name/path of the blob
            generate_sas: Whether to generate a SAS token

        Returns:
            str: File URL
        """
        return await self.blob_adapter.get_file_url(blob_name, generate_sas)

    async def file_exists(self, blob_name: str) -> bool:
        """
        Check if a file exists.

        Args:
            blob_name: Name/path of the blob

        Returns:
            bool: True if file exists
        """
        return await self.blob_adapter.file_exists(blob_name)
