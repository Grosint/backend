"""Test cases for authentication API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.endpoints.auth import router
from app.core.exceptions import UnauthorizedException
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)


class TestLoginEndpoint:
    """Test cases for login endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.fixture
    def mock_database(self):
        """Create mock database."""
        return Mock()

    @pytest.fixture
    def valid_login_request(self):
        """Create valid login request."""
        return LoginRequest(email="test@example.com", password="password123")

    @pytest.fixture
    def valid_login_response(self):
        """Create valid login response."""
        return LoginResponse(
            access_token="access_token_123",
            refresh_token="refresh_token_123",
            token_type="bearer",
            expires_in=900,
            user_id="507f1f77bcf86cd799439011",
            email="test@example.com",
        )

    @patch("app.api.endpoints.auth.AuthService")
    def test_login_success(
        self, mock_auth_service_class, client, valid_login_request, valid_login_response
    ):
        """Test successful login."""
        mock_auth_service = AsyncMock()
        mock_auth_service.login.return_value = valid_login_response
        mock_auth_service_class.return_value = mock_auth_service

        response = client.post("/login", json=valid_login_request.dict())

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Login successful"
        assert data["data"]["access_token"] == "access_token_123"
        assert data["data"]["refresh_token"] == "refresh_token_123"
        assert data["data"]["user_id"] == "507f1f77bcf86cd799439011"

    @patch("app.api.endpoints.auth.AuthService")
    def test_login_invalid_credentials(self, mock_auth_service_class, client):
        """Test login with invalid credentials."""
        mock_auth_service = AsyncMock()
        mock_auth_service.login.side_effect = UnauthorizedException(
            "Invalid email or password"
        )
        mock_auth_service_class.return_value = mock_auth_service

        login_request = LoginRequest(
            email="test@example.com", password="wrong_password"
        )

        response = client.post("/login", json=login_request.dict())

        assert response.status_code == 401
        data = response.json()
        assert "Invalid email or password" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_login_account_deactivated(self, mock_auth_service_class, client):
        """Test login with deactivated account."""
        mock_auth_service = AsyncMock()
        mock_auth_service.login.side_effect = UnauthorizedException(
            "Account is deactivated"
        )
        mock_auth_service_class.return_value = mock_auth_service

        login_request = LoginRequest(email="test@example.com", password="password123")

        response = client.post("/login", json=login_request.dict())

        assert response.status_code == 401
        data = response.json()
        assert "Account is deactivated" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_login_server_error(self, mock_auth_service_class, client):
        """Test login with server error."""
        mock_auth_service = AsyncMock()
        mock_auth_service.login.side_effect = Exception("Database connection failed")
        mock_auth_service_class.return_value = mock_auth_service

        login_request = LoginRequest(email="test@example.com", password="password123")

        response = client.post("/login", json=login_request.dict())

        assert response.status_code == 500
        data = response.json()
        assert "Login failed" in data["detail"]

    def test_login_invalid_email_format(self, client):
        """Test login with invalid email format."""
        login_request = {"email": "invalid_email", "password": "password123"}

        response = client.post("/login", json=login_request)

        assert response.status_code == 422

    def test_login_empty_password(self, client):
        """Test login with empty password."""
        login_request = {"email": "test@example.com", "password": ""}

        response = client.post("/login", json=login_request)

        assert response.status_code == 422


class TestRefreshTokenEndpoint:
    """Test cases for refresh token endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.fixture
    def valid_refresh_request(self):
        """Create valid refresh token request."""
        return RefreshTokenRequest(refresh_token="valid_refresh_token")

    @pytest.fixture
    def valid_refresh_response(self):
        """Create valid refresh token response."""
        return RefreshTokenResponse(
            access_token="new_access_token_123", token_type="bearer", expires_in=900
        )

    @patch("app.api.endpoints.auth.AuthService")
    def test_refresh_token_success(
        self,
        mock_auth_service_class,
        client,
        valid_refresh_request,
        valid_refresh_response,
    ):
        """Test successful token refresh."""
        mock_auth_service = AsyncMock()
        mock_auth_service.refresh_access_token.return_value = valid_refresh_response
        mock_auth_service_class.return_value = mock_auth_service

        response = client.post("/refresh", json=valid_refresh_request.dict())

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Token refreshed successfully"
        assert data["data"]["access_token"] == "new_access_token_123"

    @patch("app.api.endpoints.auth.AuthService")
    def test_refresh_token_invalid(self, mock_auth_service_class, client):
        """Test refresh with invalid token."""
        mock_auth_service = AsyncMock()
        mock_auth_service.refresh_access_token.side_effect = UnauthorizedException(
            "Invalid refresh token"
        )
        mock_auth_service_class.return_value = mock_auth_service

        refresh_request = RefreshTokenRequest(refresh_token="invalid_token")

        response = client.post("/refresh", json=refresh_request.dict())

        assert response.status_code == 401
        data = response.json()
        assert "Invalid refresh token" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_refresh_token_user_not_found(self, mock_auth_service_class, client):
        """Test refresh with user not found."""
        mock_auth_service = AsyncMock()
        mock_auth_service.refresh_access_token.side_effect = UnauthorizedException(
            "User not found or inactive"
        )
        mock_auth_service_class.return_value = mock_auth_service

        refresh_request = RefreshTokenRequest(refresh_token="valid_token")

        response = client.post("/refresh", json=refresh_request.dict())

        assert response.status_code == 401
        data = response.json()
        assert "User not found or inactive" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_refresh_token_server_error(self, mock_auth_service_class, client):
        """Test refresh with server error."""
        mock_auth_service = AsyncMock()
        mock_auth_service.refresh_access_token.side_effect = Exception("Database error")
        mock_auth_service_class.return_value = mock_auth_service

        refresh_request = RefreshTokenRequest(refresh_token="valid_token")

        response = client.post("/refresh", json=refresh_request.dict())

        assert response.status_code == 500
        data = response.json()
        assert "Token refresh failed" in data["detail"]


class TestLogoutEndpoint:
    """Test cases for logout endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @pytest.fixture
    def valid_logout_request(self):
        """Create valid logout request."""
        return LogoutRequest(refresh_token="refresh_token_123")

    @pytest.fixture
    def valid_logout_response(self):
        """Create valid logout response."""
        return LogoutResponse(
            message="Successfully logged out", logged_out_at=datetime.now(UTC)
        )

    @patch("app.api.endpoints.auth.AuthService")
    @patch("app.api.endpoints.auth.get_current_user_token")
    def test_logout_success(
        self,
        mock_get_token,
        mock_auth_service_class,
        client,
        valid_logout_request,
        valid_logout_response,
    ):
        """Test successful logout."""
        mock_auth_service = AsyncMock()
        mock_auth_service.logout.return_value = valid_logout_response
        mock_auth_service_class.return_value = mock_auth_service

        # Mock the token data
        mock_token_data = Mock()
        mock_token_data.user_id = "507f1f77bcf86cd799439011"
        mock_get_token.return_value = mock_token_data

        headers = {"Authorization": "Bearer access_token_123"}
        response = client.post(
            "/logout", json=valid_logout_request.dict(), headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logout successful"

    @pytest.mark.skip(reason="Temporarily disabled")
    @patch("app.api.endpoints.auth.AuthService")
    @patch("app.api.endpoints.auth.get_database")
    def test_logout_without_access_token(
        self, mock_get_database, client, valid_logout_request
    ):
        """Test logout without access token."""
        # Mock the database dependency
        mock_get_database.return_value = None

        # Test without authorization header
        response = client.post("/logout", json=valid_logout_request.dict())
        assert response.status_code == 401
        data = response.json()
        assert "Access token required" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_logout_with_valid_token(
        self, mock_auth_service_class, client, valid_logout_request
    ):
        """Test logout with valid token."""
        mock_auth_service = AsyncMock()
        mock_auth_service.logout.return_value = Mock(
            message="Logout successful", logged_out_at=datetime.now(UTC)
        )
        mock_auth_service_class.return_value = mock_auth_service

        # Test with valid authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = client.post(
            "/logout", json=valid_logout_request.dict(), headers=headers
        )

        # Debug output
        print(f"Status with token: {response.status_code}")
        print(f"Response with token: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logout successful"

    @patch("app.api.endpoints.auth.AuthService")
    def test_logout_invalid_token(
        self, mock_auth_service_class, client, valid_logout_request
    ):
        """Test logout with invalid token."""
        mock_auth_service = AsyncMock()
        mock_auth_service.logout.side_effect = UnauthorizedException("Invalid token")
        mock_auth_service_class.return_value = mock_auth_service

        headers = {"Authorization": "Bearer invalid_token"}
        response = client.post(
            "/logout", json=valid_logout_request.dict(), headers=headers
        )

        assert response.status_code == 401
        data = response.json()
        assert "Invalid token" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_logout_server_error(
        self, mock_auth_service_class, client, valid_logout_request
    ):
        """Test logout with server error."""
        mock_auth_service = AsyncMock()
        mock_auth_service.logout.side_effect = Exception("Database error")
        mock_auth_service_class.return_value = mock_auth_service

        headers = {"Authorization": "Bearer access_token_123"}
        response = client.post(
            "/logout", json=valid_logout_request.dict(), headers=headers
        )

        assert response.status_code == 500
        data = response.json()
        assert "Logout failed" in data["detail"]


class TestChangePasswordEndpoint:
    """Test cases for change password endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI

        from app.core.auth_dependencies import get_current_user_token

        app = FastAPI()
        app.include_router(router)

        # Override the get_current_user_token dependency
        def mock_get_current_user_token():
            from datetime import UTC, datetime

            from app.core.auth_dependencies import TokenData

            return TokenData(
                user_id="507f1f77bcf86cd799439011",
                email="test@example.com",
                token_type="access",
                expires_at=datetime.now(UTC),
            )

        app.dependency_overrides[get_current_user_token] = mock_get_current_user_token

        return TestClient(app)

    @pytest.fixture
    def valid_password_request(self):
        """Create valid password change request."""
        return ChangePasswordRequest(
            current_password="old_password123", new_password="NewSecure123!"
        )

    @pytest.fixture
    def valid_password_response(self):
        """Create valid password change response."""
        return ChangePasswordResponse(
            message="Password changed successfully", changed_at=datetime.now(UTC)
        )

    @patch("app.api.endpoints.auth.AuthService")
    def test_change_password_success(
        self,
        mock_auth_service_class,
        client,
        valid_password_request,
        valid_password_response,
    ):
        """Test successful password change."""
        mock_auth_service = AsyncMock()
        mock_auth_service.change_password.return_value = True
        mock_auth_service_class.return_value = mock_auth_service

        # Provide authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = client.post(
            "/change-password", json=valid_password_request.dict(), headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Password changed successfully"

    @patch("app.api.endpoints.auth.AuthService")
    def test_change_password_wrong_current_password(
        self, mock_auth_service_class, client
    ):
        """Test password change with wrong current password."""
        mock_auth_service = AsyncMock()
        mock_auth_service.change_password.side_effect = UnauthorizedException(
            "Current password is incorrect"
        )
        mock_auth_service_class.return_value = mock_auth_service

        password_request = ChangePasswordRequest(
            current_password="wrong_password", new_password="NewSecure123!"
        )

        # Provide authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = client.post(
            "/change-password", json=password_request.dict(), headers=headers
        )

        assert response.status_code == 401
        data = response.json()
        assert "Current password is incorrect" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_change_password_user_not_found(self, mock_auth_service_class, client):
        """Test password change with user not found."""
        mock_auth_service = AsyncMock()
        mock_auth_service.change_password.side_effect = UnauthorizedException(
            "User not found"
        )
        mock_auth_service_class.return_value = mock_auth_service

        password_request = ChangePasswordRequest(
            current_password="old_password123", new_password="NewSecure123!"
        )

        # Provide authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = client.post(
            "/change-password", json=password_request.dict(), headers=headers
        )

        assert response.status_code == 401
        data = response.json()
        assert "User not found" in data["detail"]

    def test_change_password_weak_new_password(self, client):
        """Test password change with weak new password."""
        password_request = {
            "current_password": "old_password123",
            "new_password": "123",  # Too weak - should fail validation
        }

        # Provide authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = client.post(
            "/change-password", json=password_request, headers=headers
        )

        assert response.status_code == 422

    def test_change_password_empty_current_password(self, client):
        """Test password change with empty current password."""
        password_request = {"current_password": "", "new_password": "NewSecure123!"}

        # Provide authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = client.post(
            "/change-password", json=password_request, headers=headers
        )

        assert response.status_code == 422


class TestGetAuthStatusEndpoint:
    """Test cases for get auth status endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI

        from app.core.auth_dependencies import get_current_user_token

        app = FastAPI()
        app.include_router(router)

        # Override the get_current_user_token dependency
        def mock_get_current_user_token():
            from datetime import UTC, datetime

            from app.core.auth_dependencies import TokenData

            return TokenData(
                user_id="507f1f77bcf86cd799439011",
                email="test@example.com",
                token_type="access",
                expires_at=datetime.now(UTC),
            )

        app.dependency_overrides[get_current_user_token] = mock_get_current_user_token

        return TestClient(app)

    def test_get_auth_status_success(self, client):
        """Test successful auth status retrieval."""
        # Provide authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = client.get("/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Authentication status retrieved"
        assert data["data"]["is_authenticated"] is True
        assert data["data"]["user_id"] == "507f1f77bcf86cd799439011"
        assert data["data"]["email"] == "test@example.com"


class TestGetTokenInfoEndpoint:
    """Test cases for get token info endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI

        from app.core.auth_dependencies import (
            get_authorization_header,
            get_current_user_token,
        )

        app = FastAPI()
        app.include_router(router)

        # Override the dependencies
        def mock_get_current_user_token():
            from datetime import UTC, datetime

            from app.core.auth_dependencies import TokenData

            return TokenData(
                user_id="507f1f77bcf86cd799439011",
                email="test@example.com",
                token_type="access",
                expires_at=datetime.now(UTC),
            )

        def mock_get_authorization_header():
            return "access_token_123"

        app.dependency_overrides[get_current_user_token] = mock_get_current_user_token
        app.dependency_overrides[get_authorization_header] = (
            mock_get_authorization_header
        )

        return TestClient(app)

    @patch("app.utils.jwt.verify_access_token")
    def test_get_token_info_success(self, mock_verify_token, client):
        """Test successful token info retrieval."""
        mock_verify_token.return_value = {"iat": 1234567890}

        # Provide authorization header
        headers = {"Authorization": "Bearer valid_token"}
        response = client.get("/token-info", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Token information retrieved"
        assert data["data"]["user_id"] == "507f1f77bcf86cd799439011"
        assert data["data"]["email"] == "test@example.com"


class TestValidateTokenEndpoint:
    """Test cases for validate token endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @patch("app.api.endpoints.auth.AuthService")
    def test_validate_token_success(self, mock_auth_service_class, client):
        """Test successful token validation."""
        mock_auth_service = AsyncMock()
        mock_user = Mock()
        mock_user.id = "507f1f77bcf86cd799439011"
        mock_user.email = "test@example.com"
        mock_user.isActive = True
        mock_user.isVerified = True
        mock_auth_service.get_user_by_token.return_value = mock_user
        mock_auth_service_class.return_value = mock_auth_service

        headers = {"Authorization": "Bearer valid_token"}
        response = client.post("/validate", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Token is valid"
        assert data["data"]["valid"] is True
        assert data["data"]["user_id"] == "507f1f77bcf86cd799439011"

    @patch("app.api.endpoints.auth.AuthService")
    def test_validate_token_without_token(self, mock_auth_service_class, client):
        """Test token validation without token."""
        response = client.post("/validate")

        assert response.status_code == 401
        data = response.json()
        assert "Access token required" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_validate_token_invalid(self, mock_auth_service_class, client):
        """Test token validation with invalid token."""
        mock_auth_service = AsyncMock()
        mock_auth_service.get_user_by_token.return_value = None
        mock_auth_service_class.return_value = mock_auth_service

        headers = {"Authorization": "Bearer invalid_token"}
        response = client.post("/validate", headers=headers)

        assert response.status_code == 401
        data = response.json()
        assert "Invalid token" in data["detail"]

    @patch("app.api.endpoints.auth.AuthService")
    def test_validate_token_server_error(self, mock_auth_service_class, client):
        """Test token validation with server error."""
        mock_auth_service = AsyncMock()
        mock_auth_service.get_user_by_token.side_effect = Exception("Database error")
        mock_auth_service_class.return_value = mock_auth_service

        headers = {"Authorization": "Bearer valid_token"}
        response = client.post("/validate", headers=headers)

        assert response.status_code == 500
        data = response.json()
        assert "Token validation failed" in data["detail"]
