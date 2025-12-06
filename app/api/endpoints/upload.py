"""API endpoints for file upload operations."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.config import settings
from app.schemas.response import SuccessResponse
from app.schemas.upload import (
    DeleteFileRequest,
    DirectUploadResponse,
    FileInfoResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
    UploadConfigResponse,
)
from app.services.upload_service import UploadService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/config",
    response_model=SuccessResponse[UploadConfigResponse],
    summary="Get upload configuration",
    description="Get the current upload configuration including allowed file types and size limits",
)
async def get_upload_config():
    """Get upload configuration."""
    try:
        allowed_extensions = [
            ext.strip() for ext in settings.ALLOWED_FILE_EXTENSIONS.split(",")
        ]

        config = UploadConfigResponse(
            max_file_size_mb=settings.MAX_UPLOAD_SIZE_MB,
            allowed_extensions=allowed_extensions,
            presigned_url_expiry_minutes=settings.AZURE_SAS_TOKEN_EXPIRY_MINUTES,
        )

        return SuccessResponse(
            message="Upload configuration retrieved successfully",
            data=config,
        )
    except Exception as e:
        logger.error(f"Failed to get upload config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve upload configuration",
        ) from e


@router.post(
    "/presigned-url",
    response_model=SuccessResponse[PresignedUrlResponse],
    summary="Generate pre-signed URL",
    description="Generate a pre-signed URL for client-side file upload to Azure Blob Storage",
)
async def generate_presigned_url(
    request: PresignedUrlRequest,
    current_user: TokenData | None = Depends(get_current_user_token),
):
    """
    Generate a pre-signed URL for uploading a file.

    The client can use this URL to upload files directly to Azure Blob Storage
    without going through the backend.
    """
    try:
        upload_service = UploadService()

        result = await upload_service.generate_presigned_url(
            filename=request.filename,
            folder=request.folder,
            prefix=request.prefix,
            expiry_minutes=request.expiry_minutes,
            metadata=request.metadata,
        )

        response = PresignedUrlResponse(**result)

        return SuccessResponse(
            message="Pre-signed URL generated successfully",
            data=response,
        )
    except ValueError as e:
        logger.warning(f"Invalid request for pre-signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to generate pre-signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate pre-signed URL",
        ) from e


@router.post(
    "/direct",
    response_model=SuccessResponse[DirectUploadResponse],
    summary="Upload file directly",
    description="Upload a file directly through the backend to Azure Blob Storage",
)
async def upload_file_direct(
    file: Annotated[UploadFile, File(..., description="File to upload")],
    folder: str | None = Form(None, description="Optional folder path"),
    prefix: str | None = Form(None, description="Optional prefix"),
    current_user: TokenData | None = Depends(get_current_user_token),
):
    """
    Upload a file directly through the backend.

    The file is uploaded to Azure Blob Storage via the backend server.
    """
    try:
        upload_service = UploadService()

        # Read file content
        file_content = await file.read()
        filename = file.filename or "unnamed_file"

        # Upload file
        result = await upload_service.upload_file_direct(
            file_content=file_content,
            filename=filename,
            folder=folder,
            prefix=prefix,
        )

        response = DirectUploadResponse(**result)

        return SuccessResponse(
            message="File uploaded successfully",
            data=response,
        )
    except ValueError as e:
        logger.warning(f"Invalid file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file",
        ) from e


@router.delete(
    "/file",
    response_model=SuccessResponse[dict],
    summary="Delete file",
    description="Delete a file from Azure Blob Storage",
)
async def delete_file(
    request: DeleteFileRequest,
    current_user: TokenData | None = Depends(get_current_user_token),
):
    """Delete a file from storage."""
    try:
        upload_service = UploadService()

        deleted = await upload_service.delete_file(request.blob_name)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or could not be deleted",
            )

        return SuccessResponse(
            message="File deleted successfully",
            data={"blob_name": request.blob_name, "deleted": True},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        ) from e


@router.get(
    "/file/info",
    response_model=SuccessResponse[FileInfoResponse],
    summary="Get file information",
    description="Get information about a file including its URL",
)
async def get_file_info(
    blob_name: str,
    generate_sas: bool = False,
    current_user: TokenData | None = Depends(get_current_user_token),
):
    """Get file information and URL."""
    try:
        upload_service = UploadService()

        exists = await upload_service.file_exists(blob_name)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        url = await upload_service.get_file_url(blob_name, generate_sas)

        response = FileInfoResponse(
            blob_name=blob_name,
            url=url,
            exists=True,
        )

        return SuccessResponse(
            message="File information retrieved successfully",
            data=response,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file information",
        ) from e
