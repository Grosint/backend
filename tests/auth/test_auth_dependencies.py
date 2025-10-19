"""Test cases for authentication dependencies."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth_dependencies import (
    TokenData,
    get_auth_status,
    get_authorization_header,
    get_current_user_email,
    get_current_user_id,
    get_current_user_optional,
    get_current_user_token,
    get_token_info,
    require_admin_role,
    verify_token_not_blocked,
)
from app.core.exceptions import UnauthorizedException


class TestTokenData:
    """Test cases for TokenData class."""

    def test_token_data_creation(self):
        """Test TokenData object creation with valid data."""
        user_id = "507f1f77bcf86cd799439011"
        email = "test@example.com"
        token_type = "access"
        expires_at = datetime.now(UTC) + timedelta(minutes=15)

        token_data = TokenData(user_id, email, token_type, expires_at)

        assert token_data.user_id == user_id
        assert token_data.email == email
        assert token_data.token_type == token_type
        assert token_data.expires_at == expires_at

    def test_token_data_with_different_types(self):
        """Test TokenData with different token types."""
        user_id = "507f1f77bcf86cd799439011"
        email = "test@example.com"
        refresh_type = "refresh"
        expires_at = datetime.now(UTC) + timedelta(days=7)

        token_data = TokenData(user_id, email, refresh_type, expires_at)

        assert token_data.token_type == refresh_type


class TestGetAuthorizationHeader:
    """Test cases for get_authorization_header function."""

    def test_get_authorization_header_with_valid_bearer_token(self):
        """Test getting authorization header with valid bearer token."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid_token"
        )

        result = get_authorization_header(credentials)

        assert result == "valid_token"

    def test_get_authorization_header_with_invalid_scheme(self):
        """Test getting authorization header with invalid scheme."""
        credentials = HTTPAuthorizationCredentials(scheme="Basic", credentials="token")

        result = get_authorization_header(credentials)

        assert result is None

    def test_get_authorization_header_with_none_credentials(self):
        """Test getting authorization header with None credentials."""
        result = get_authorization_header(None)

        assert result is None

    def test_get_authorization_header_case_insensitive_bearer(self):
        """Test that bearer scheme is case insensitive."""
        credentials = HTTPAuthorizationCredentials(scheme="bearer", credentials="token")

        result = get_authorization_header(credentials)

        assert result == "token"

    def test_get_authorization_header_with_empty_credentials(self):
        """Test getting authorization header with empty credentials."""
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")

        result = get_authorization_header(credentials)

        assert result is None


class TestVerifyTokenNotBlocked:
    """Test cases for verify_token_not_blocked function."""

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.get_token_jti")
    @patch("app.core.auth_dependencies.is_token_blocked")
    async def test_verify_token_not_blocked_success(
        self, mock_is_blocked, mock_get_jti
    ):
        """Test successful token verification when token is not blocked."""
        mock_get_jti.return_value = "jti_123"
        mock_is_blocked.return_value = False
        mock_database = Mock()

        result = await verify_token_not_blocked("valid_token", mock_database)

        assert result is True
        mock_get_jti.assert_called_once_with("valid_token")
        mock_is_blocked.assert_called_once_with("jti_123", mock_database)

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.get_token_jti")
    @patch("app.core.auth_dependencies.is_token_blocked")
    async def test_verify_token_not_blocked_when_blocked(
        self, mock_is_blocked, mock_get_jti
    ):
        """Test token verification when token is blocked."""
        mock_get_jti.return_value = "jti_123"
        mock_is_blocked.return_value = True
        mock_database = Mock()

        with pytest.raises(UnauthorizedException, match="Token has been revoked"):
            await verify_token_not_blocked("blocked_token", mock_database)

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.get_token_jti")
    async def test_verify_token_not_blocked_with_exception(self, mock_get_jti):
        """Test token verification when get_token_jti raises exception."""
        mock_get_jti.side_effect = Exception("JWT decode error")
        mock_database = Mock()

        with pytest.raises(UnauthorizedException, match="Token verification failed"):
            await verify_token_not_blocked("invalid_token", mock_database)


class TestGetCurrentUserToken:
    """Test cases for get_current_user_token function."""

    @pytest.mark.asyncio
    async def test_get_current_user_token_with_no_token(self):
        """Test get_current_user_token with no token provided."""
        with pytest.raises(UnauthorizedException, match="Authorization header missing"):
            await get_current_user_token(None, Mock())

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.verify_token_not_blocked")
    @patch("app.core.auth_dependencies.verify_access_token")
    async def test_get_current_user_token_success(
        self, mock_verify_token, mock_verify_not_blocked
    ):
        """Test successful token validation and user data extraction."""
        mock_verify_not_blocked.return_value = True
        mock_verify_token.return_value = {
            "sub": "507f1f77bcf86cd799439011",
            "email": "test@example.com",
            "type": "access",
            "exp": 1234567890,
        }
        mock_database = Mock()

        result = await get_current_user_token("valid_token", mock_database)

        assert isinstance(result, TokenData)
        assert result.user_id == "507f1f77bcf86cd799439011"
        assert result.email == "test@example.com"
        assert result.token_type == "access"
        assert isinstance(result.expires_at, datetime)

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.verify_token_not_blocked")
    async def test_get_current_user_token_when_blocked(self, mock_verify_not_blocked):
        """Test get_current_user_token when token is blocked."""
        mock_verify_not_blocked.side_effect = UnauthorizedException(
            "Token has been revoked"
        )
        mock_database = Mock()

        with pytest.raises(UnauthorizedException, match="Token has been revoked"):
            await get_current_user_token("blocked_token", mock_database)

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.verify_token_not_blocked")
    @patch("app.core.auth_dependencies.verify_access_token")
    async def test_get_current_user_token_invalid_payload(
        self, mock_verify_token, mock_verify_not_blocked
    ):
        """Test get_current_user_token with invalid token payload."""
        mock_verify_not_blocked.return_value = True
        mock_verify_token.return_value = {
            "sub": "507f1f77bcf86cd799439011",
            "email": "test@example.com",
            # Missing required fields
        }
        mock_database = Mock()

        with pytest.raises(UnauthorizedException, match="Invalid token payload"):
            await get_current_user_token("invalid_payload_token", mock_database)

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.verify_token_not_blocked")
    @patch("app.core.auth_dependencies.verify_access_token")
    async def test_get_current_user_token_with_exception(
        self, mock_verify_token, mock_verify_not_blocked
    ):
        """Test get_current_user_token with unexpected exception."""
        mock_verify_not_blocked.return_value = True
        mock_verify_token.side_effect = Exception("JWT decode error")
        mock_database = Mock()

        with pytest.raises(UnauthorizedException, match="Authentication failed"):
            await get_current_user_token("error_token", mock_database)


class TestGetCurrentUserId:
    """Test cases for get_current_user_id function."""

    def test_get_current_user_id_success(self):
        """Test getting user ID from token data."""
        token_data = TokenData(
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

        result = get_current_user_id(token_data)

        assert result == "507f1f77bcf86cd799439011"


class TestGetCurrentUserEmail:
    """Test cases for get_current_user_email function."""

    def test_get_current_user_email_success(self):
        """Test getting user email from token data."""
        token_data = TokenData(
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

        result = get_current_user_email(token_data)

        assert result == "test@example.com"


class TestGetAuthStatus:
    """Test cases for get_auth_status function."""

    def test_get_auth_status_authenticated(self):
        """Test auth status when user is authenticated."""
        token_data = TokenData(
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

        result = get_auth_status(token_data)

        assert result.is_authenticated is True
        assert result.user_id == "507f1f77bcf86cd799439011"
        assert result.email == "test@example.com"
        assert result.token_type == "access"
        assert result.expires_at == token_data.expires_at

    def test_get_auth_status_not_authenticated(self):
        """Test auth status when user is not authenticated."""
        result = get_auth_status(None)

        assert result.is_authenticated is False
        assert result.user_id is None
        assert result.email is None
        assert result.token_type is None
        assert result.expires_at is None


class TestGetTokenInfo:
    """Test cases for get_token_info function."""

    @pytest.mark.asyncio
    async def test_get_token_info_with_no_token(self):
        """Test get_token_info with no token provided."""
        result = await get_token_info(None, Mock())

        assert result is None

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.verify_token_not_blocked")
    @patch("app.core.auth_dependencies.verify_access_token")
    async def test_get_token_info_success(
        self, mock_verify_token, mock_verify_not_blocked
    ):
        """Test successful token info retrieval."""
        mock_verify_not_blocked.return_value = True
        mock_verify_token.return_value = {
            "sub": "507f1f77bcf86cd799439011",
            "email": "test@example.com",
            "type": "access",
            "iat": 1234567890,
            "exp": 1234567890 + 900,  # 15 minutes later
        }
        mock_database = Mock()

        result = await get_token_info("valid_token", mock_database)

        assert result is not None
        assert result.user_id == "507f1f77bcf86cd799439011"
        assert result.email == "test@example.com"
        assert result.token_type == "access"
        assert isinstance(result.issued_at, datetime)
        assert isinstance(result.expires_at, datetime)
        assert isinstance(result.is_expired, bool)

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.verify_token_not_blocked")
    @patch("app.core.auth_dependencies.verify_access_token")
    async def test_get_token_info_invalid_payload(
        self, mock_verify_token, mock_verify_not_blocked
    ):
        """Test get_token_info with invalid token payload."""
        mock_verify_not_blocked.return_value = True
        mock_verify_token.return_value = {
            "sub": "507f1f77bcf86cd799439011",
            "email": "test@example.com",
            # Missing required fields
        }
        mock_database = Mock()

        result = await get_token_info("invalid_token", mock_database)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.verify_token_not_blocked")
    async def test_get_token_info_when_blocked(self, mock_verify_not_blocked):
        """Test get_token_info when token is blocked."""
        mock_verify_not_blocked.side_effect = UnauthorizedException("Token blocked")
        mock_database = Mock()

        result = await get_token_info("blocked_token", mock_database)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.core.auth_dependencies.verify_token_not_blocked")
    @patch("app.core.auth_dependencies.verify_access_token")
    async def test_get_token_info_with_exception(
        self, mock_verify_token, mock_verify_not_blocked
    ):
        """Test get_token_info with unexpected exception."""
        mock_verify_not_blocked.return_value = True
        mock_verify_token.side_effect = Exception("JWT decode error")
        mock_database = Mock()

        result = await get_token_info("error_token", mock_database)

        assert result is None


class TestGetCurrentUserOptional:
    """Test cases for get_current_user_optional function."""

    def test_get_current_user_optional_with_token_data(self):
        """Test get_current_user_optional with valid token data."""
        token_data = TokenData(
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

        result = get_current_user_optional(token_data)

        assert result == token_data

    def test_get_current_user_optional_with_none(self):
        """Test get_current_user_optional with None token data."""
        result = get_current_user_optional(None)

        assert result is None


class TestRequireAdminRole:
    """Test cases for require_admin_role function."""

    def test_require_admin_role_success(self):
        """Test require_admin_role with valid token data."""
        token_data = TokenData(
            user_id="507f1f77bcf86cd799439011",
            email="admin@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

        result = require_admin_role(token_data)

        assert result == token_data

    def test_require_admin_role_with_none_token(self):
        """Test require_admin_role with None token data."""
        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(None)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in str(exc_info.value.detail)
