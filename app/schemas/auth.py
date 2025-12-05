"""Authentication schemas for requests and responses."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.password import validate_password_strength


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password is not empty."""
        if not v or not v.strip():
            raise ValueError("Password cannot be empty")
        return v.strip()


class LoginResponse(BaseModel):
    """Login response schema."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str = Field(..., min_length=1, description="Valid refresh token")

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, v: str) -> str:
        """Validate refresh token is not empty."""
        if not v or not v.strip():
            raise ValueError("Refresh token cannot be empty")
        return v.strip()


class RefreshTokenResponse(BaseModel):
    """Refresh token response schema."""

    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")


class LogoutRequest(BaseModel):
    """Logout request schema."""

    refresh_token: str | None = Field(None, description="Refresh token to invalidate")


class LogoutResponse(BaseModel):
    """Logout response schema."""

    message: str = Field(..., description="Logout confirmation message")
    logged_out_at: datetime = Field(..., description="Logout timestamp")


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        is_valid, issues = validate_password_strength(v)
        if not is_valid:
            raise ValueError(f"Password validation failed: {', '.join(issues)}")
        return v

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, v: str) -> str:
        """Validate current password is not empty."""
        if not v or not v.strip():
            raise ValueError("Current password cannot be empty")
        return v.strip()


class ChangePasswordResponse(BaseModel):
    """Change password response schema."""

    message: str = Field(..., description="Password change confirmation message")
    changed_at: datetime = Field(..., description="Password change timestamp")


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema."""

    email: EmailStr = Field(..., description="User email address")


class ForgotPasswordResponse(BaseModel):
    """Forgot password response schema."""

    message: str = Field(..., description="Password reset instructions")
    reset_token_expires_in: int = Field(
        ..., description="Reset token expiration time in seconds"
    )


class ResetPasswordRequest(BaseModel):
    """Reset password request schema."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        is_valid, issues = validate_password_strength(v)
        if not is_valid:
            raise ValueError(f"Password validation failed: {', '.join(issues)}")
        return v


class ResetPasswordResponse(BaseModel):
    """Reset password response schema."""

    message: str = Field(..., description="Password reset confirmation message")
    reset_at: datetime = Field(..., description="Password reset timestamp")


class TokenInfo(BaseModel):
    """Token information schema."""

    token_type: str = Field(..., description="Token type")
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    issued_at: datetime = Field(..., description="Token issued at")
    expires_at: datetime = Field(..., description="Token expires at")
    is_expired: bool = Field(..., description="Whether token is expired")


class AuthStatus(BaseModel):
    """Authentication status schema."""

    is_authenticated: bool = Field(..., description="Whether user is authenticated")
    user_id: str | None = Field(None, description="User ID if authenticated")
    email: str | None = Field(None, description="User email if authenticated")
    token_type: str | None = Field(None, description="Token type if authenticated")
    expires_at: datetime | None = Field(
        None, description="Token expiration if authenticated"
    )


class SendOtpRequest(BaseModel):
    """Send OTP request schema."""

    email: EmailStr = Field(..., description="User email address")


class SendOtpResponse(BaseModel):
    """Send OTP response schema."""

    message: str = Field(..., description="OTP sent confirmation message")
    expires_in: int = Field(..., description="OTP expiration time in seconds")


class VerifyOtpRequest(BaseModel):
    """Verify OTP request schema."""

    email: EmailStr = Field(..., description="User email address")
    otp: str = Field(..., min_length=6, max_length=6, description="OTP code")

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        """Validate OTP is numeric."""
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        return v.strip()


class VerifyOtpResponse(BaseModel):
    """Verify OTP response schema."""

    message: str = Field(..., description="OTP verification confirmation message")
    verified_at: datetime = Field(..., description="OTP verification timestamp")
    is_verified: bool = Field(..., description="Whether user account is verified")
