"""Azure Blob Storage adapter for file uploads."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

from azure.core.exceptions import AzureError
from azure.storage.blob import (
    AccountSasPermissions,
    BlobServiceClient,
    ContentSettings,
    ResourceTypes,
    generate_account_sas,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


class AzureBlobAdapter:
    """Adapter for Azure Blob Storage operations."""

    def __init__(self):
        """Initialize the Azure Blob Storage adapter."""
        self.account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
        self.account_key = settings.AZURE_STORAGE_ACCOUNT_KEY
        self.container_name = settings.AZURE_STORAGE_CONTAINER_NAME
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING

        # Initialize blob service client
        if self.connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
        elif self.account_name and self.account_key:
            account_url = f"https://{self.account_name}.blob.core.windows.net"
            self.blob_service_client = BlobServiceClient(
                account_url=account_url, credential=self.account_key
            )
        else:
            raise ValueError(
                "Azure Blob Storage credentials not configured. "
                "Provide either AZURE_STORAGE_CONNECTION_STRING or "
                "both AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY"
            )

        # Ensure container exists
        self._ensure_container_exists()

    def _ensure_container_exists(self) -> None:
        """Ensure the container exists, create if it doesn't."""
        try:
            container_client = self.blob_service_client.get_container_client(
                self.container_name
            )
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {self.container_name}")
        except AzureError as e:
            logger.error(f"Failed to ensure container exists: {e}")
            raise

    def _get_content_type(self, filename: str) -> str:
        """Get content type based on file extension."""
        extension = os.path.splitext(filename)[1].lower()
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".zip": "application/zip",
            ".rar": "application/x-rar-compressed",
        }
        return content_types.get(extension, "application/octet-stream")

    async def upload_file(
        self,
        file_content: bytes,
        blob_name: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file directly to Azure Blob Storage.

        Args:
            file_content: File content as bytes
            blob_name: Name/path of the blob in the container
            content_type: MIME type of the file (auto-detected if not provided)
            metadata: Optional metadata to attach to the blob

        Returns:
            dict: Upload result with blob URL and metadata
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )

            # Auto-detect content type if not provided
            if not content_type:
                content_type = self._get_content_type(blob_name)

            # Upload the file
            content_settings = ContentSettings(content_type=content_type)
            blob_client.upload_blob(
                data=file_content,
                content_settings=content_settings,
                metadata=metadata or {},
                overwrite=True,
            )

            # Get the blob URL
            blob_url = blob_client.url

            logger.info(f"Successfully uploaded file: {blob_name}")

            return {
                "blob_name": blob_name,
                "url": blob_url,
                "content_type": content_type,
                "size": len(file_content),
                "uploaded_at": datetime.utcnow().isoformat(),
            }

        except AzureError as e:
            logger.error(f"Failed to upload file {blob_name}: {e}")
            raise

    async def generate_presigned_url(
        self,
        blob_name: str,
        expiry_minutes: int | None = None,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a pre-signed URL (SAS token) for direct client upload.

        Args:
            blob_name: Name/path of the blob in the container
            expiry_minutes: URL expiration time in minutes (default from config)
            content_type: Expected content type (optional)
            metadata: Optional metadata to attach to the blob

        Returns:
            dict: Pre-signed URL and upload information
        """
        try:
            if not expiry_minutes:
                expiry_minutes = settings.AZURE_SAS_TOKEN_EXPIRY_MINUTES

            # Generate SAS token
            sas_token = generate_account_sas(
                account_name=self.account_name,
                account_key=self.account_key,
                resource_types=ResourceTypes(object=True),
                permission=AccountSasPermissions(
                    read=True, write=True, create=True, add=True
                ),
                expiry=datetime.utcnow() + timedelta(minutes=expiry_minutes),
            )

            # Construct the pre-signed URL
            blob_url = (
                f"https://{self.account_name}.blob.core.windows.net/"
                f"{self.container_name}/{quote(blob_name, safe='')}"
            )
            presigned_url = f"{blob_url}?{sas_token}"

            # Prepare upload metadata
            upload_info = {
                "blob_name": blob_name,
                "presigned_url": presigned_url,
                "expires_at": (
                    datetime.utcnow() + timedelta(minutes=expiry_minutes)
                ).isoformat(),
                "expiry_minutes": expiry_minutes,
            }

            # Add content type if provided
            if content_type:
                upload_info["content_type"] = content_type
            else:
                upload_info["content_type"] = self._get_content_type(blob_name)

            # Add metadata if provided
            if metadata:
                upload_info["metadata"] = metadata

            # Add upload instructions
            upload_info["upload_instructions"] = {
                "method": "PUT",
                "required_headers": {
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Type": upload_info.get(
                        "content_type", "application/octet-stream"
                    ),
                },
                "optional_headers": {
                    "x-ms-blob-cache-control": "optional",
                    "x-ms-blob-content-encoding": "optional",
                    "x-ms-blob-content-language": "optional",
                    "x-ms-blob-content-md5": "optional",
                },
            }

            logger.info(
                f"Generated pre-signed URL for {blob_name}, expires in {expiry_minutes} minutes"
            )

            return upload_info

        except Exception as e:
            logger.error(f"Failed to generate pre-signed URL for {blob_name}: {e}")
            raise

    async def delete_file(self, blob_name: str) -> bool:
        """
        Delete a file from Azure Blob Storage.

        Args:
            blob_name: Name/path of the blob to delete

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            blob_client.delete_blob()
            logger.info(f"Successfully deleted file: {blob_name}")
            return True
        except AzureError as e:
            logger.error(f"Failed to delete file {blob_name}: {e}")
            return False

    async def get_file_url(self, blob_name: str, generate_sas: bool = False) -> str:
        """
        Get the URL for a file in Azure Blob Storage.

        Args:
            blob_name: Name/path of the blob
            generate_sas: Whether to generate a SAS token for the URL

        Returns:
            str: File URL (with or without SAS token)
        """
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=blob_name
        )

        if generate_sas:
            # Generate SAS token
            sas_token = generate_account_sas(
                account_name=self.account_name,
                account_key=self.account_key,
                resource_types=ResourceTypes(object=True),
                permission=AccountSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1),
            )
            return f"{blob_client.url}?{sas_token}"

        return blob_client.url

    async def file_exists(self, blob_name: str) -> bool:
        """
        Check if a file exists in Azure Blob Storage.

        Args:
            blob_name: Name/path of the blob to check

        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, blob=blob_name
            )
            return blob_client.exists()
        except AzureError:
            return False
