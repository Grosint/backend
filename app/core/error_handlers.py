"""Global exception handlers for standardized error responses."""

import logging

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import BaseAPIException
from app.schemas.response import (
    ErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)

logger = logging.getLogger(__name__)


async def base_api_exception_handler(
    request: Request, exc: BaseAPIException
) -> JSONResponse:
    """Handle custom API exceptions."""
    logger.error(
        f"API Exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
        },
    )

    error_response = ErrorResponse(
        message=exc.message, error_code=exc.error_code, details=exc.details
    )

    return JSONResponse(
        status_code=exc.status_code, content=error_response.model_dump()
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    logger.warning(
        f"Validation Error: {exc.errors()}",
        extra={"path": request.url.path, "body": exc.body},
    )

    validation_errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        validation_errors.append(
            ValidationErrorDetail(
                field=field, message=error["msg"], value=error.get("input")
            )
        )

    error_response = ValidationErrorResponse(
        message="Validation failed",
        validation_errors=validation_errors,
        details={"error_count": len(validation_errors)},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={"status_code": exc.status_code, "path": request.url.path},
    )

    error_response = ErrorResponse(
        message=str(exc.detail),
        error_code="HTTP_ERROR",
        details={"status_code": exc.status_code},
    )

    return JSONResponse(
        status_code=exc.status_code, content=error_response.model_dump()
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error(
        f"Unexpected error: {str(exc)}",
        exc_info=True,
        extra={"path": request.url.path, "exception_type": type(exc).__name__},
    )

    error_response = ErrorResponse(
        message="An unexpected error occurred",
        error_code="INTERNAL_SERVER_ERROR",
        details={"exception_type": type(exc).__name__},
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )
