"""Test cases for authentication service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId

from app.core.exceptions import NotFoundException, UnauthorizedException
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest
from app.services.auth_service import AuthService


class TestAuthService:
    """Test cases for AuthService class."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mock database."""
        mock_db = Mock()
        return AuthService(mock_db)

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = ObjectId("507f1f77bcf86cd799439011")
        user.email = "test@example.com"
        user.password = "hashed_password"
        user.isActive = True
        user.isVerified = True
        return user

    @pytest.fixture
    def valid_login_request(self):
        """Create valid login request."""
        return LoginRequest(email="test@example.com", password="password123")

    @pytest.fixture
    def valid_refresh_request(self):
        """Create valid refresh token request."""
        return RefreshTokenRequest(refresh_token="valid_refresh_token")


class TestAuthenticateUser:
    """Test cases for authenticate_user method."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mock database."""
        mock_db = Mock()
        return AuthService(mock_db)

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = ObjectId("507f1f77bcf86cd799439011")
        user.email = "test@example.com"
        user.password = "hashed_password"
        user.isActive = True
        user.isVerified = True
        return user

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_email")
    @patch("app.services.auth_service.verify_password")
    async def test_authenticate_user_success(
        self, mock_verify_password, mock_find_user, auth_service, mock_user
    ):
        """Test successful user authentication."""
        # Mock the user lookup
        mock_find_user.return_value = mock_user
        mock_verify_password.return_value = True

        result = await auth_service.authenticate_user("test@example.com", "password123")

        assert result == mock_user
        mock_find_user.assert_called_once_with("test@example.com")
        mock_verify_password.assert_called_once_with("password123", "hashed_password")

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_email")
    async def test_authenticate_user_not_found(self, mock_find_user, auth_service):
        """Test authentication with user not found."""
        mock_find_user.return_value = None

        result = await auth_service.authenticate_user(
            "nonexistent@example.com", "password123"
        )

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_email")
    @patch("app.services.auth_service.verify_password")
    async def test_authenticate_user_wrong_password(
        self, mock_verify_password, mock_find_user, auth_service, mock_user
    ):
        """Test authentication with wrong password."""
        mock_find_user.return_value = mock_user
        mock_verify_password.return_value = False

        result = await auth_service.authenticate_user(
            "test@example.com", "wrong_password"
        )

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_email")
    @patch("app.services.auth_service.verify_password")
    async def test_authenticate_user_inactive(
        self, mock_verify_password, mock_find_user, auth_service
    ):
        """Test authentication with inactive user."""
        mock_user = Mock(spec=User)
        mock_user.password = "hashed_password"
        mock_user.isActive = False
        mock_find_user.return_value = mock_user
        mock_verify_password.return_value = True

        result = await auth_service.authenticate_user("test@example.com", "password123")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_email")
    async def test_authenticate_user_exception(self, mock_find_user, auth_service):
        """Test authentication with database exception."""
        mock_find_user.side_effect = Exception("Database error")

        result = await auth_service.authenticate_user("test@example.com", "password123")

        assert result is None


class TestLogin:
    """Test cases for login method."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mock database."""
        mock_db = Mock()
        return AuthService(mock_db)

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = ObjectId("507f1f77bcf86cd799439011")
        user.email = "test@example.com"
        user.password = "hashed_password"
        user.isActive = True
        user.isVerified = True
        return user

    @pytest.fixture
    def valid_login_request(self):
        """Create valid login request."""
        return LoginRequest(email="test@example.com", password="password123")

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @patch("app.services.auth_service.create_access_token")
    @patch("app.services.auth_service.create_refresh_token")
    @patch("app.services.auth_service.AuthService.authenticate_user")
    async def test_login_success(
        self,
        mock_authenticate,
        mock_create_refresh,
        mock_create_access,
        auth_service,
        mock_user,
        valid_login_request,
    ):
        """Test successful login."""
        mock_authenticate.return_value = mock_user
        mock_create_access.return_value = "access_token_123"
        mock_create_refresh.return_value = "refresh_token_123"

        result = await auth_service.login(valid_login_request)

        assert result.access_token == "access_token_123"
        assert result.refresh_token == "refresh_token_123"
        assert result.token_type == "bearer"
        assert result.expires_in == 900
        assert result.user_id == str(mock_user.id)
        assert result.email == mock_user.email

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService.authenticate_user")
    async def test_login_invalid_credentials(
        self, mock_authenticate, auth_service, valid_login_request
    ):
        """Test login with invalid credentials."""
        mock_authenticate.return_value = None

        with pytest.raises(UnauthorizedException, match="Invalid email or password"):
            await auth_service.login(valid_login_request)

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService.authenticate_user")
    async def test_login_inactive_user(
        self, mock_authenticate, auth_service, valid_login_request
    ):
        """Test login with inactive user."""
        mock_user = Mock(spec=User)
        mock_user.isActive = False
        mock_authenticate.return_value = mock_user

        with pytest.raises(UnauthorizedException, match="Account is deactivated"):
            await auth_service.login(valid_login_request)


class TestRefreshAccessToken:
    """Test cases for refresh_access_token method."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mock database."""
        mock_db = Mock()
        return AuthService(mock_db)

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = ObjectId("507f1f77bcf86cd799439011")
        user.email = "test@example.com"
        user.isActive = True
        return user

    @pytest.mark.asyncio
    @patch("app.services.auth_service.create_access_token")
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    @patch("app.utils.jwt.verify_refresh_token")
    async def test_refresh_access_token_success(
        self,
        mock_verify_refresh,
        mock_find_user,
        mock_create_access,
        auth_service,
        mock_user,
    ):
        """Test successful access token refresh."""
        mock_verify_refresh.return_value = {
            "sub": str(mock_user.id),
            "email": mock_user.email,
        }
        mock_find_user.return_value = mock_user
        mock_create_access.return_value = "new_access_token_123"

        result = await auth_service.refresh_access_token("valid_refresh_token")

        assert result.access_token == "new_access_token_123"
        assert result.token_type == "bearer"
        assert result.expires_in == 900

    @pytest.mark.asyncio
    @patch("app.utils.jwt.verify_refresh_token")
    async def test_refresh_access_token_invalid_token(
        self, mock_verify_refresh, auth_service
    ):
        """Test refresh with invalid token."""
        mock_verify_refresh.return_value = {"sub": None, "email": None}

        with pytest.raises(UnauthorizedException, match="Invalid refresh token"):
            await auth_service.refresh_access_token("invalid_token")

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    @patch("app.utils.jwt.verify_refresh_token")
    async def test_refresh_access_token_user_not_found(
        self, mock_verify_refresh, mock_find_user, auth_service
    ):
        """Test refresh with user not found."""
        mock_verify_refresh.return_value = {
            "sub": "507f1f77bcf86cd799439011",
            "email": "test@example.com",
        }
        mock_find_user.return_value = None

        with pytest.raises(UnauthorizedException, match="User not found or inactive"):
            await auth_service.refresh_access_token("valid_token")

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    @patch("app.utils.jwt.verify_refresh_token")
    async def test_refresh_access_token_inactive_user(
        self, mock_verify_refresh, mock_find_user, auth_service
    ):
        """Test refresh with inactive user."""
        mock_user = Mock(spec=User)
        mock_user.isActive = False
        mock_verify_refresh.return_value = {
            "sub": "507f1f77bcf86cd799439011",
            "email": "test@example.com",
        }
        mock_find_user.return_value = mock_user

        with pytest.raises(UnauthorizedException, match="User not found or inactive"):
            await auth_service.refresh_access_token("valid_token")

    @pytest.mark.asyncio
    @patch("app.utils.jwt.verify_refresh_token")
    async def test_refresh_access_token_exception(
        self, mock_verify_refresh, auth_service
    ):
        """Test refresh with exception."""
        mock_verify_refresh.side_effect = Exception("JWT decode error")

        with pytest.raises(UnauthorizedException, match="Token refresh failed"):
            await auth_service.refresh_access_token("error_token")


class TestLogout:
    """Test cases for logout method."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mock database."""
        mock_db = Mock()
        return AuthService(mock_db)

    @pytest.mark.asyncio
    @patch("app.services.auth_service.add_token_to_blocklist")
    @patch("app.utils.jwt.jwt_manager.get_token_expiry")
    @patch("app.services.auth_service.get_token_jti")
    @patch("app.utils.jwt.get_current_user_id")
    async def test_logout_success(
        self,
        mock_get_user_id,
        mock_get_jti,
        mock_get_expiry,
        mock_add_blocklist,
        auth_service,
    ):
        """Test successful logout."""
        mock_get_user_id.return_value = "507f1f77bcf86cd799439011"
        mock_get_jti.return_value = "jti_123"
        mock_get_expiry.return_value = datetime.now(UTC) + timedelta(minutes=15)

        result = await auth_service.logout("access_token_123", "refresh_token_123")

        assert result.message == "Successfully logged out"
        assert isinstance(result.logged_out_at, datetime)
        assert mock_add_blocklist.call_count == 2  # Both access and refresh tokens

    @pytest.mark.asyncio
    @patch("app.services.auth_service.add_token_to_blocklist")
    @patch("app.utils.jwt.jwt_manager.get_token_expiry")
    @patch("app.services.auth_service.get_token_jti")
    @patch("app.utils.jwt.get_current_user_id")
    async def test_logout_without_refresh_token(
        self,
        mock_get_user_id,
        mock_get_jti,
        mock_get_expiry,
        mock_add_blocklist,
        auth_service,
    ):
        """Test logout without refresh token."""
        mock_get_user_id.return_value = "507f1f77bcf86cd799439011"
        mock_get_jti.return_value = "jti_123"
        mock_get_expiry.return_value = datetime.now(UTC) + timedelta(minutes=15)

        result = await auth_service.logout("access_token_123")

        assert result.message == "Successfully logged out"
        assert mock_add_blocklist.call_count == 1  # Only access token

    @pytest.mark.asyncio
    @patch("app.utils.jwt.get_current_user_id")
    async def test_logout_exception(self, mock_get_user_id, auth_service):
        """Test logout with exception."""
        mock_get_user_id.side_effect = Exception("JWT decode error")

        with pytest.raises(UnauthorizedException, match="Logout failed"):
            await auth_service.logout("invalid_token")


class TestChangePassword:
    """Test cases for change_password method."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mock database."""
        mock_db = Mock()
        return AuthService(mock_db)

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = ObjectId("507f1f77bcf86cd799439011")
        user.email = "test@example.com"
        user.password = "hashed_password"
        user.isActive = True
        return user

    @pytest.mark.asyncio
    @patch("app.services.auth_service.hash_password")
    @patch("app.services.auth_service.verify_password")
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    async def test_change_password_success(
        self,
        mock_find_user,
        mock_verify_password,
        mock_hash_password,
        auth_service,
        mock_user,
    ):
        """Test successful password change."""
        mock_find_user.return_value = mock_user
        mock_verify_password.return_value = True
        mock_hash_password.return_value = "new_hashed_password"
        mock_user.save = AsyncMock()

        result = await auth_service.change_password(
            "507f1f77bcf86cd799439011", "old_password", "new_password"
        )

        assert result is True
        assert mock_user.password == "new_hashed_password"
        mock_user.save.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    async def test_change_password_user_not_found(self, mock_find_user, auth_service):
        """Test password change with user not found."""
        mock_find_user.return_value = None

        with pytest.raises(NotFoundException, match="User not found"):
            await auth_service.change_password(
                "507f1f77bcf86cd799439011", "old_password", "new_password"
            )

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    @patch("app.services.auth_service.verify_password")
    async def test_change_password_wrong_current_password(
        self, mock_verify_password, mock_find_user, auth_service, mock_user
    ):
        """Test password change with wrong current password."""
        mock_find_user.return_value = mock_user
        mock_verify_password.return_value = False

        with pytest.raises(
            UnauthorizedException, match="Current password is incorrect"
        ):
            await auth_service.change_password(
                "507f1f77bcf86cd799439011", "wrong_password", "new_password"
            )

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    async def test_change_password_exception(self, mock_find_user, auth_service):
        """Test password change with exception."""
        mock_find_user.side_effect = Exception("Database error")

        with pytest.raises(UnauthorizedException, match="Password change failed"):
            await auth_service.change_password(
                "507f1f77bcf86cd799439011", "old_password", "new_password"
            )


class TestGetUserByToken:
    """Test cases for get_user_by_token method."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mock database."""
        mock_db = Mock()
        return AuthService(mock_db)

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = ObjectId("507f1f77bcf86cd799439011")
        user.email = "test@example.com"
        return user

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    @patch("app.services.auth_service.get_current_user_id")
    async def test_get_user_by_token_success(
        self, mock_get_user_id, mock_find_user, auth_service, mock_user
    ):
        """Test successful user retrieval by token."""
        mock_get_user_id.return_value = "507f1f77bcf86cd799439011"
        mock_find_user.return_value = mock_user

        result = await auth_service.get_user_by_token("valid_token")

        assert result == mock_user

    @pytest.mark.asyncio
    @patch("app.services.auth_service.get_current_user_id")
    async def test_get_user_by_token_invalid_token(
        self, mock_get_user_id, auth_service
    ):
        """Test user retrieval with invalid token."""
        mock_get_user_id.side_effect = Exception("JWT decode error")

        result = await auth_service.get_user_by_token("invalid_token")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    @patch("app.services.auth_service.get_current_user_id")
    async def test_get_user_by_token_user_not_found(
        self, mock_get_user_id, mock_find_user, auth_service
    ):
        """Test user retrieval when user not found."""
        mock_get_user_id.return_value = "507f1f77bcf86cd799439011"
        mock_find_user.return_value = None

        result = await auth_service.get_user_by_token("valid_token")

        assert result is None


class TestValidateUserSession:
    """Test cases for validate_user_session method."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService instance with mock database."""
        mock_db = Mock()
        return AuthService(mock_db)

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = ObjectId("507f1f77bcf86cd799439011")
        user.isActive = True
        return user

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    async def test_validate_user_session_success(
        self, mock_find_user, auth_service, mock_user
    ):
        """Test successful user session validation."""
        mock_find_user.return_value = mock_user

        result = await auth_service.validate_user_session("507f1f77bcf86cd799439011")

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    async def test_validate_user_session_user_not_found(
        self, mock_find_user, auth_service
    ):
        """Test user session validation with user not found."""
        mock_find_user.return_value = None

        result = await auth_service.validate_user_session("507f1f77bcf86cd799439011")

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    async def test_validate_user_session_inactive_user(
        self, mock_find_user, auth_service
    ):
        """Test user session validation with inactive user."""
        mock_user = Mock(spec=User)
        mock_user.isActive = False
        mock_find_user.return_value = mock_user

        result = await auth_service.validate_user_session("507f1f77bcf86cd799439011")

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.auth_service.AuthService._find_user_by_id")
    async def test_validate_user_session_exception(self, mock_find_user, auth_service):
        """Test user session validation with exception."""
        mock_find_user.side_effect = Exception("Database error")

        result = await auth_service.validate_user_session("507f1f77bcf86cd799439011")

        assert result is False
