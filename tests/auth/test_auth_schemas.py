"""Test cases for authentication schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    AuthStatus,
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenInfo,
)


class TestLoginRequest:
    """Test cases for LoginRequest schema."""

    def test_valid_login_request(self):
        """Test valid login request creation."""
        login_request = LoginRequest(email="test@example.com", password="password123")

        assert login_request.email == "test@example.com"
        assert login_request.password == "password123"

    def test_login_request_invalid_email(self):
        """Test login request with invalid email format."""
        with pytest.raises(ValidationError):
            LoginRequest(email="invalid_email", password="password123")

    def test_login_request_empty_password(self):
        """Test login request with empty password."""
        with pytest.raises(ValidationError):
            LoginRequest(email="test@example.com", password="")

    def test_login_request_whitespace_password(self):
        """Test login request with whitespace-only password."""
        with pytest.raises(ValidationError):
            LoginRequest(email="test@example.com", password="   ")

    def test_login_request_password_stripped(self):
        """Test that password whitespace is stripped."""
        login_request = LoginRequest(
            email="test@example.com", password="  password123  "
        )

        assert login_request.password == "password123"


class TestLoginResponse:
    """Test cases for LoginResponse schema."""

    def test_valid_login_response(self):
        """Test valid login response creation."""
        login_response = LoginResponse(
            access_token="access_token_123",
            refresh_token="refresh_token_123",
            token_type="bearer",
            expires_in=900,
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
        )

        assert login_response.access_token == "access_token_123"
        assert login_response.refresh_token == "refresh_token_123"
        assert login_response.token_type == "bearer"
        assert login_response.expires_in == 900
        assert login_response.user_id == "507f1f77bcf86cd799439011"
        assert login_response.email == "test@example.com"

    def test_login_response_default_token_type(self):
        """Test login response with default token type."""
        login_response = LoginResponse(
            access_token="access_token_123",
            refresh_token="refresh_token_123",
            expires_in=900,
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
        )

        assert login_response.token_type == "bearer"


class TestRefreshTokenRequest:
    """Test cases for RefreshTokenRequest schema."""

    def test_valid_refresh_token_request(self):
        """Test valid refresh token request creation."""
        refresh_request = RefreshTokenRequest(refresh_token="valid_refresh_token")

        assert refresh_request.refresh_token == "valid_refresh_token"

    def test_refresh_token_request_empty_token(self):
        """Test refresh token request with empty token."""
        with pytest.raises(ValidationError):
            RefreshTokenRequest(refresh_token="")


class TestRefreshTokenResponse:
    """Test cases for RefreshTokenResponse schema."""

    def test_valid_refresh_token_response(self):
        """Test valid refresh token response creation."""
        refresh_response = RefreshTokenResponse(
            access_token="new_access_token_123", token_type="bearer", expires_in=900
        )

        assert refresh_response.access_token == "new_access_token_123"
        assert refresh_response.token_type == "bearer"
        assert refresh_response.expires_in == 900

    def test_refresh_token_response_default_token_type(self):
        """Test refresh token response with default token type."""
        refresh_response = RefreshTokenResponse(
            access_token="new_access_token_123", expires_in=900
        )

        assert refresh_response.token_type == "bearer"


class TestLogoutRequest:
    """Test cases for LogoutRequest schema."""

    def test_valid_logout_request_with_refresh_token(self):
        """Test valid logout request with refresh token."""
        logout_request = LogoutRequest(refresh_token="refresh_token_123")

        assert logout_request.refresh_token == "refresh_token_123"

    def test_valid_logout_request_without_refresh_token(self):
        """Test valid logout request without refresh token."""
        logout_request = LogoutRequest()

        assert logout_request.refresh_token is None


class TestLogoutResponse:
    """Test cases for LogoutResponse schema."""

    def test_valid_logout_response(self):
        """Test valid logout response creation."""
        logout_time = datetime.now(UTC)
        logout_response = LogoutResponse(
            message="Successfully logged out", logged_out_at=logout_time
        )

        assert logout_response.message == "Successfully logged out"
        assert logout_response.logged_out_at == logout_time


class TestChangePasswordRequest:
    """Test cases for ChangePasswordRequest schema."""

    def test_valid_change_password_request(self):
        """Test valid change password request creation."""
        password_request = ChangePasswordRequest(
            current_password="old_password123", new_password="NewSecure123!"
        )

        assert password_request.current_password == "old_password123"
        assert password_request.new_password == "NewSecure123!"

    def test_change_password_request_weak_new_password(self):
        """Test change password request with weak new password."""
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="old_password123",
                new_password="123",  # Too weak
            )

    def test_change_password_request_short_new_password(self):
        """Test change password request with short new password."""
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="old_password123",
                new_password="1234567",  # Less than 8 characters
            )

    def test_change_password_request_long_new_password(self):
        """Test change password request with long new password."""
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="old_password123",
                new_password="a" * 129,  # More than 128 characters
            )

    def test_change_password_request_empty_current_password(self):
        """Test change password request with empty current password."""
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="", new_password="new_password123")

    def test_change_password_request_whitespace_current_password(self):
        """Test change password request with whitespace-only current password."""
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="   ", new_password="new_password123"
            )

    def test_change_password_request_current_password_stripped(self):
        """Test that current password whitespace is stripped."""
        password_request = ChangePasswordRequest(
            current_password="  old_password123  ", new_password="NewSecure123!"
        )

        assert password_request.current_password == "old_password123"


class TestChangePasswordResponse:
    """Test cases for ChangePasswordResponse schema."""

    def test_valid_change_password_response(self):
        """Test valid change password response creation."""
        change_time = datetime.now(UTC)
        password_response = ChangePasswordResponse(
            message="Password changed successfully", changed_at=change_time
        )

        assert password_response.message == "Password changed successfully"
        assert password_response.changed_at == change_time


class TestForgotPasswordRequest:
    """Test cases for ForgotPasswordRequest schema."""

    def test_valid_forgot_password_request(self):
        """Test valid forgot password request creation."""
        forgot_request = ForgotPasswordRequest(email="test@example.com")

        assert forgot_request.email == "test@example.com"

    def test_forgot_password_request_invalid_email(self):
        """Test forgot password request with invalid email format."""
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email="invalid_email")


class TestForgotPasswordResponse:
    """Test cases for ForgotPasswordResponse schema."""

    def test_valid_forgot_password_response(self):
        """Test valid forgot password response creation."""
        forgot_response = ForgotPasswordResponse(
            message="Password reset instructions sent", reset_token_expires_in=3600
        )

        assert forgot_response.message == "Password reset instructions sent"
        assert forgot_response.reset_token_expires_in == 3600


class TestResetPasswordRequest:
    """Test cases for ResetPasswordRequest schema."""

    def test_valid_reset_password_request(self):
        """Test valid reset password request creation."""
        reset_request = ResetPasswordRequest(
            token="reset_token_123", new_password="NewSecure123!"
        )

        assert reset_request.token == "reset_token_123"
        assert reset_request.new_password == "NewSecure123!"

    def test_reset_password_request_weak_new_password(self):
        """Test reset password request with weak new password."""
        with pytest.raises(ValidationError):
            ResetPasswordRequest(
                token="reset_token_123",
                new_password="123",  # Too weak
            )

    def test_reset_password_request_short_new_password(self):
        """Test reset password request with short new password."""
        with pytest.raises(ValidationError):
            ResetPasswordRequest(
                token="reset_token_123",
                new_password="1234567",  # Less than 8 characters
            )

    def test_reset_password_request_long_new_password(self):
        """Test reset password request with long new password."""
        with pytest.raises(ValidationError):
            ResetPasswordRequest(
                token="reset_token_123",
                new_password="a" * 129,  # More than 128 characters
            )


class TestResetPasswordResponse:
    """Test cases for ResetPasswordResponse schema."""

    def test_valid_reset_password_response(self):
        """Test valid reset password response creation."""
        reset_time = datetime.now(UTC)
        reset_response = ResetPasswordResponse(
            message="Password reset successfully", reset_at=reset_time
        )

        assert reset_response.message == "Password reset successfully"
        assert reset_response.reset_at == reset_time


class TestTokenInfo:
    """Test cases for TokenInfo schema."""

    def test_valid_token_info(self):
        """Test valid token info creation."""
        issued_at = datetime.now(UTC)
        expires_at = datetime.now(UTC)

        token_info = TokenInfo(
            token_type="access",
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
            issued_at=issued_at,
            expires_at=expires_at,
            is_expired=False,
        )

        assert token_info.token_type == "access"
        assert token_info.user_id == "507f1f77bcf86cd799439011"
        assert token_info.email == "test@example.com"
        assert token_info.issued_at == issued_at
        assert token_info.expires_at == expires_at
        assert token_info.is_expired is False

    def test_token_info_expired(self):
        """Test token info with expired token."""
        issued_at = datetime.now(UTC)
        expires_at = datetime.now(UTC)

        token_info = TokenInfo(
            token_type="access",
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
            issued_at=issued_at,
            expires_at=expires_at,
            is_expired=True,
        )

        assert token_info.is_expired is True


class TestAuthStatus:
    """Test cases for AuthStatus schema."""

    def test_auth_status_authenticated(self):
        """Test auth status when authenticated."""
        expires_at = datetime.now(UTC)

        auth_status = AuthStatus(
            is_authenticated=True,
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
            token_type="access",
            expires_at=expires_at,
        )

        assert auth_status.is_authenticated is True
        assert auth_status.user_id == "507f1f77bcf86cd799439011"
        assert auth_status.email == "test@example.com"
        assert auth_status.token_type == "access"
        assert auth_status.expires_at == expires_at

    def test_auth_status_not_authenticated(self):
        """Test auth status when not authenticated."""
        auth_status = AuthStatus(
            is_authenticated=False,
            user_id=None,
            email=None,
            token_type=None,
            expires_at=None,
        )

        assert auth_status.is_authenticated is False
        assert auth_status.user_id is None
        assert auth_status.email is None
        assert auth_status.token_type is None
        assert auth_status.expires_at is None

    def test_auth_status_partial_data(self):
        """Test auth status with partial data."""
        auth_status = AuthStatus(
            is_authenticated=True,
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
            # token_type and expires_at are None by default
        )

        assert auth_status.is_authenticated is True
        assert auth_status.user_id == "507f1f77bcf86cd799439011"
        assert auth_status.email == "test@example.com"
        assert auth_status.token_type is None
        assert auth_status.expires_at is None
