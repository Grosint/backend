"""Schemas for file upload operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PresignedUrlRequest(BaseModel):
    """Request schema for generating pre-signed URLs."""

    filename: str = Field(..., description="Name of the file to upload")
    folder: str | None = Field(
        None,
        description="Optional folder path for organization (e.g., 'images', 'documents/user123')",
    )
    prefix: str | None = Field(
        None, description="Optional prefix (e.g., user ID, category)"
    )
    expiry_minutes: int | None = Field(
        None,
        description="URL expiration time in minutes (default from config)",
        ge=1,
        le=1440,  # Max 24 hours
    )
    metadata: dict[str, str] | None = Field(
        None, description="Optional metadata to attach to the file"
    )


class PresignedUrlResponse(BaseModel):
    """Response schema for pre-signed URL generation."""

    blob_name: str = Field(..., description="Generated blob name/path")
    presigned_url: str = Field(..., description="Pre-signed URL for upload")
    original_filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="Expected content type")
    expires_at: str = Field(..., description="URL expiration timestamp (ISO format)")
    expiry_minutes: int = Field(..., description="URL expiration time in minutes")
    folder: str | None = Field(None, description="Folder path used")
    prefix: str | None = Field(None, description="Prefix used")
    metadata: dict[str, str] | None = Field(None, description="Metadata attached")
    upload_instructions: dict[str, Any] = Field(
        ...,
        description="Instructions for uploading using the pre-signed URL, including required headers",
    )


class DirectUploadResponse(BaseModel):
    """Response schema for direct file upload."""

    blob_name: str = Field(..., description="Blob name/path in storage")
    url: str = Field(..., description="Public URL of the uploaded file")
    original_filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="Content type of the file")
    size: int = Field(..., description="File size in bytes")
    uploaded_at: str = Field(..., description="Upload timestamp (ISO format)")
    folder: str | None = Field(None, description="Folder path used")
    prefix: str | None = Field(None, description="Prefix used")


class DeleteFileRequest(BaseModel):
    """Request schema for deleting a file."""

    blob_name: str = Field(..., description="Blob name/path to delete")


class FileInfoResponse(BaseModel):
    """Response schema for file information."""

    blob_name: str = Field(..., description="Blob name/path")
    url: str = Field(..., description="File URL")
    exists: bool = Field(..., description="Whether the file exists")


class UploadConfigResponse(BaseModel):
    """Response schema for upload configuration."""

    max_file_size_mb: int = Field(..., description="Maximum file size in MB")
    allowed_extensions: list[str] = Field(
        ..., description="List of allowed file extensions"
    )
    presigned_url_expiry_minutes: int = Field(
        ..., description="Default pre-signed URL expiry time in minutes"
    )
