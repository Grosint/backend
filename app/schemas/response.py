"""Standard API response schemas for consistent error handling."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel, Field, field_serializer

T = TypeVar("T")


class BaseResponse[T](BaseModel):
    """Base response wrapper for all API responses."""

    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Human-readable message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )
    data: T | None = Field(None, description="Response data (null for errors)")

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return value.isoformat() + "Z"


class SuccessResponse[T](BaseResponse[T]):
    """Standard success response format."""

    success: bool = Field(True, description="Always true for success responses")
    message: str = Field(
        "Operation completed successfully", description="Success message"
    )
    data: T = Field(..., description="Response data")


class ErrorResponse(BaseResponse[None]):
    """Standard error response format."""

    success: bool = Field(False, description="Always false for error responses")
    message: str = Field(..., description="Error message")
    data: None = Field(None, description="Always null for errors")
    error_code: str = Field(..., description="Machine-readable error code")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class ValidationErrorDetail(BaseModel):
    """Validation error detail for field-specific errors."""

    field: str = Field(..., description="Field name that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Any = Field(None, description="Invalid value that was provided")


class ValidationErrorResponse(ErrorResponse):
    """Response format for validation errors."""

    error_code: str = Field(
        "VALIDATION_ERROR", description="Error code for validation failures"
    )
    details: dict[str, Any] = Field(..., description="Validation error details")
    validation_errors: list[ValidationErrorDetail] = Field(
        ..., description="List of field validation errors"
    )


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class PaginatedResponse[T](BaseResponse[list[T]]):
    """Paginated response format."""

    success: bool = Field(
        True, description="Always true for successful paginated responses"
    )
    message: str = Field("Data retrieved successfully", description="Success message")
    data: list[T] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
