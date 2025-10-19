"""Custom exception classes for standardized error handling."""

from typing import Any


class BaseAPIException(Exception):
    """Base exception class for all API exceptions."""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(BaseAPIException):
    """Exception for validation errors."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class NotFoundException(BaseAPIException):
    """Exception for resource not found errors."""

    def __init__(self, resource: str = "Resource", resource_id: str | None = None):
        message = f"{resource} not found"
        if resource_id:
            message += f" with ID: {resource_id}"

        super().__init__(message=message, error_code="NOT_FOUND", status_code=404)


class ConflictException(BaseAPIException):
    """Exception for resource conflict errors (e.g., duplicate email)."""

    def __init__(
        self,
        message: str = "Resource already exists",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message, error_code="CONFLICT", status_code=409, details=details
        )


class AuthenticationException(BaseAPIException):
    """Exception for authentication errors."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message, error_code="AUTHENTICATION_ERROR", status_code=401
        )


class UnauthorizedException(BaseAPIException):
    """Exception for unauthorized access errors."""

    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(message=message, error_code="UNAUTHORIZED", status_code=401)


class AuthorizationException(BaseAPIException):
    """Exception for authorization errors."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message, error_code="AUTHORIZATION_ERROR", status_code=403
        )


class BusinessLogicException(BaseAPIException):
    """Exception for business logic errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "BUSINESS_LOGIC_ERROR",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
        )


class DatabaseException(BaseAPIException):
    """Exception for database-related errors."""

    def __init__(
        self,
        message: str = "Database operation failed",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )


class ExternalServiceException(BaseAPIException):
    """Exception for external service errors."""

    def __init__(
        self,
        service_name: str,
        message: str = "External service error",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=f"{service_name}: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=details,
        )
