"""Test cases for user API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api.endpoints.user import router
from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.error_handlers import (
    base_api_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import BaseAPIException, ConflictException
from app.models.user import User, UserInDB
from app.schemas.user import UserCreateRequest, UserUpdateRequest


def create_test_app():
    """Create a test FastAPI app with exception handlers."""
    app = FastAPI()
    app.include_router(router)

    # Add exception handlers
    app.add_exception_handler(BaseAPIException, base_api_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Mock database dependency
    from app.core.database import get_database

    mock_db = Mock()
    # Make the mock database subscriptable
    mock_db.__getitem__ = Mock(return_value=Mock())
    app.dependency_overrides[get_database] = lambda: mock_db

    return app


class TestCreateUserEndpoint:
    """Test cases for create user endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(create_test_app())

    @pytest.fixture
    def test_data_factory(self):
        """Test data factory fixture."""
        from tests.conftest import TestDataFactory

        return TestDataFactory()

    @pytest.fixture
    def valid_user_request(self, test_data_factory):
        """Create valid user creation request."""
        user_data = test_data_factory.create_user_create_request()
        return UserCreateRequest(**user_data)

    @pytest.fixture
    def mock_user(self, test_data_factory):
        """Create mock user using Mock(spec=User)."""
        user_data = test_data_factory.create_user_data(id=str(ObjectId()))
        user = Mock(spec=User)
        user.id = ObjectId(user_data["id"])
        user.email = user_data["email"]
        user.phone = user_data["phone"]
        user.userType = user_data.get("userType", "user")
        user.features = user_data.get("features", [])
        user.firstName = user_data["firstName"]
        user.lastName = user_data["lastName"]
        user.pinCode = user_data["pinCode"]
        user.state = user_data["state"]
        user.isActive = user_data["isActive"]
        user.isVerified = user_data["isVerified"]
        user.createdAt = user_data["createdAt"]
        user.updatedAt = user_data["updatedAt"]
        return user

    @patch("app.api.endpoints.user.UserService")
    def test_create_user_success(
        self,
        mock_user_service_class,
        client,
        valid_user_request,
        mock_user,
        test_data_factory,
    ):
        """Test successful user creation."""
        # Create UserInDB object for return value
        user_data = test_data_factory.create_user_data(id=str(mock_user.id))
        user_in_db = UserInDB(**user_data)

        mock_user_service = AsyncMock()
        mock_user_service.create_user.return_value = user_in_db
        mock_user_service_class.return_value = mock_user_service

        with (
            patch("app.api.endpoints.user.generate_otp", return_value="123456"),
            patch(
                "app.api.endpoints.user.store_otp",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.api.endpoints.user.send_otp_email",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            response = client.post("/", json=valid_user_request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "User created successfully" in data["message"]
        assert data["data"]["email"] == user_data["email"]
        assert data["data"]["phone"] == user_data["phone"]

    @patch("app.api.endpoints.user.UserService")
    def test_create_user_email_already_exists(
        self, mock_user_service_class, client, valid_user_request, test_data_factory
    ):
        """Test user creation with existing email."""
        mock_user_service = AsyncMock()
        mock_user_service.create_user.side_effect = ConflictException(
            message="User with this email already exists",
            details={"email": valid_user_request.email},
        )
        mock_user_service_class.return_value = mock_user_service

        response = client.post("/", json=valid_user_request.model_dump())

        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert "User with this email already exists" in data["message"]

    def test_create_user_invalid_email_format(self, client):
        """Test user creation with invalid email format."""
        user_request = {
            "email": "invalid_email",
            "phone": "+1234567890",
            "password": "password123",
        }

        response = client.post("/", json=user_request)

        assert response.status_code == 422

    def test_create_user_invalid_phone_format(self, client):
        """Test user creation with invalid phone format."""
        user_request = {
            "email": "test@example.com",
            "phone": "invalid_phone",
            "password": "password123",
        }

        response = client.post("/", json=user_request)

        assert response.status_code == 422

    def test_create_user_weak_password(self, client):
        """Test user creation with weak password."""
        user_request = {
            "email": "test@example.com",
            "phone": "+1234567890",
            "password": "123",  # Too weak
        }

        response = client.post("/", json=user_request)

        assert response.status_code == 422

    def test_create_user_missing_required_fields(self, client):
        """Test user creation with missing required fields."""
        user_request = {
            "email": "test@example.com",
            # Missing phone, password
        }

        response = client.post("/", json=user_request)

        assert response.status_code == 422


class TestGetCurrentUserInfoEndpoint:
    """Test cases for get current user info endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(create_test_app())

    @pytest.fixture
    def test_data_factory(self):
        """Test data factory fixture."""
        from tests.conftest import TestDataFactory

        return TestDataFactory()

    @pytest.fixture
    def mock_token_data(self, test_data_factory):
        """Create mock token data."""
        return TokenData(
            user_id=str(ObjectId()),
            email="test@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

    @pytest.fixture
    def mock_user(self, test_data_factory):
        """Create mock user using Mock(spec=User)."""
        user_id = str(ObjectId())
        user_data = test_data_factory.create_user_data(
            id=user_id,
            firstName="John",
            lastName="Doe",
            pinCode="12345",
            state="CA",
            isVerified=True,
        )
        user = Mock(spec=User)
        user.id = ObjectId(user_data["id"])
        user.email = user_data["email"]
        user.phone = user_data["phone"]
        user.userType = user_data.get("userType", "user")
        user.features = user_data.get("features", [])
        user.firstName = user_data["firstName"]
        user.lastName = user_data["lastName"]
        user.pinCode = user_data["pinCode"]
        user.state = user_data["state"]
        user.isActive = user_data["isActive"]
        user.isVerified = user_data["isVerified"]
        user.createdAt = user_data["createdAt"]
        user.updatedAt = user_data["updatedAt"]
        return user

    @patch("app.api.endpoints.user.UserService")
    def test_get_current_user_info_success(
        self,
        mock_user_service_class,
        client,
        mock_token_data,
        mock_user,
        test_data_factory,
    ):
        """Test successful current user info retrieval."""
        # Create UserInDB object for return value
        user_data = test_data_factory.create_user_data(
            id=str(mock_user.id),
            firstName="John",
            lastName="Doe",
            pinCode="12345",
            state="CA",
            isVerified=True,
        )
        user_in_db = UserInDB(**user_data)

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.return_value = user_in_db
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.get("/me")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "User information retrieved successfully"
        assert data["data"]["email"] == user_data["email"]
        assert data["data"]["firstName"] == "John"

    @patch("app.api.endpoints.user.UserService")
    def test_get_current_user_info_not_found(
        self, mock_user_service_class, client, mock_token_data
    ):
        """Test current user info retrieval when user not found."""
        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.return_value = None
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.get("/me")

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "User" in data["message"]

    @patch("app.api.endpoints.user.UserService")
    def test_get_current_user_info_server_error(
        self, mock_user_service_class, client, mock_token_data
    ):
        """Test current user info retrieval with server error."""
        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.side_effect = Exception("Database error")
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        # Use pytest.raises to expect the exception
        with pytest.raises(Exception) as exc_info:
            client.get("/me")

        # Verify it's the expected database error
        assert "Database error" in str(exc_info.value)


class TestUpdateCurrentUserEndpoint:
    """Test cases for update current user endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(create_test_app())

    @pytest.fixture
    def test_data_factory(self):
        """Test data factory fixture."""
        from tests.conftest import TestDataFactory

        return TestDataFactory()

    @pytest.fixture
    def mock_token_data(self, test_data_factory):
        """Create mock token data."""
        return TokenData(
            user_id=str(ObjectId()),
            email="test@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

    @pytest.fixture
    def valid_update_request(self, test_data_factory):
        """Create valid user update request."""
        user_data = test_data_factory.create_user_update_request(
            firstName="John", lastName="Doe", pinCode="12345", state="CA"
        )
        return UserUpdateRequest(**user_data)

    @pytest.fixture
    def mock_user(self, test_data_factory):
        """Create mock user using Mock(spec=User)."""
        user_id = str(ObjectId())
        user_data = test_data_factory.create_user_data(
            id=user_id,
            firstName="John",
            lastName="Doe",
            pinCode="12345",
            state="CA",
            isVerified=True,
        )
        user = Mock(spec=User)
        user.id = ObjectId(user_data["id"])
        user.email = user_data["email"]
        user.phone = user_data["phone"]
        user.userType = user_data.get("userType", "user")
        user.features = user_data.get("features", [])
        user.firstName = user_data["firstName"]
        user.lastName = user_data["lastName"]
        user.pinCode = user_data["pinCode"]
        user.state = user_data["state"]
        user.isActive = user_data["isActive"]
        user.isVerified = user_data["isVerified"]
        user.createdAt = user_data["createdAt"]
        user.updatedAt = user_data["updatedAt"]
        return user

    @patch("app.api.endpoints.user.UserService")
    def test_update_current_user_success(
        self,
        mock_user_service_class,
        client,
        mock_token_data,
        valid_update_request,
        mock_user,
        test_data_factory,
    ):
        """Test successful current user update."""
        # Create UserInDB object for return value
        user_data = test_data_factory.create_user_data(
            id=str(mock_user.id),
            firstName="John",
            lastName="Doe",
            pinCode="12345",
            state="CA",
            isVerified=True,
        )
        user_in_db = UserInDB(**user_data)

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.return_value = user_in_db
        mock_user_service.update_user.return_value = user_in_db
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.put("/me", json=valid_update_request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "User updated successfully"
        assert data["data"]["firstName"] == "John"

    @patch("app.api.endpoints.user.UserService")
    def test_update_current_user_not_found(
        self, mock_user_service_class, client, mock_token_data, valid_update_request
    ):
        """Test current user update when user not found."""
        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.return_value = None
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.put("/me", json=valid_update_request.model_dump())

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    @patch("app.api.endpoints.user.UserService")
    def test_update_current_user_update_failed(
        self,
        mock_user_service_class,
        client,
        mock_token_data,
        valid_update_request,
        mock_user,
        test_data_factory,
    ):
        """Test current user update when update fails."""
        # Create UserInDB object for get_user_by_id return value
        user_data = test_data_factory.create_user_data(id=str(mock_user.id))
        user_in_db = UserInDB(**user_data)

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.return_value = user_in_db
        mock_user_service.update_user.return_value = None
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.put("/me", json=valid_update_request.model_dump())

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_update_current_user_invalid_phone_format(self, client, mock_token_data):
        """Test current user update with invalid phone format."""
        update_request = {"phone": "invalid_phone"}

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.put("/me", json=update_request)

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False

    def test_update_current_user_empty_request(
        self, client, mock_token_data, test_data_factory
    ):
        """Test current user update with empty request."""
        update_request = {}

        with patch("app.api.endpoints.user.UserService") as mock_user_service_class:
            # Create a proper mock user object using TestDataFactory
            user_data = test_data_factory.create_user_data(
                firstName="John",
                lastName="Doe",
                pinCode="12345",
                state="CA",
                isVerified=True,
            )
            user_in_db = UserInDB(**user_data)

            mock_user_service = AsyncMock()
            mock_user_service.get_user_by_id.return_value = user_in_db
            mock_user_service.update_user.return_value = user_in_db
            mock_user_service_class.return_value = mock_user_service

            # Override the dependency
            client.app.dependency_overrides[get_current_user_token] = (
                lambda: mock_token_data
            )

            response = client.put("/me", json=update_request)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestListUsersEndpoint:
    """Test cases for list users endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(create_test_app())

    @pytest.fixture
    def test_data_factory(self):
        """Test data factory fixture."""
        from tests.conftest import TestDataFactory

        return TestDataFactory()

    @pytest.fixture
    def mock_token_data(self, test_data_factory):
        """Create mock token data."""
        return TokenData(
            user_id=str(ObjectId()),
            email="admin@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

    @pytest.fixture
    def mock_users(self, test_data_factory):
        """Create mock users list using TestDataFactory."""
        users = []
        for i in range(3):
            user_data = test_data_factory.create_user_data(
                id=str(ObjectId()),
                email=f"user{i}@example.com",
                phone=f"+123456789{i}",
                firstName=f"User{i}",
                lastName="Test",
                pinCode="12345",
                state="CA",
                isVerified=True,
            )
            user_in_db = UserInDB(**user_data)
            users.append(user_in_db)
        return users

    @patch("app.api.endpoints.user.UserService")
    def test_list_users_success(
        self, mock_user_service_class, client, mock_token_data, mock_users
    ):
        """Test successful users listing."""
        mock_user_service = AsyncMock()
        mock_user_service.list_users.return_value = mock_users
        mock_user_service.count_users.return_value = 3
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.get("/list?page=1&size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Users retrieved successfully"
        assert len(data["data"]) == 3
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["size"] == 10
        assert data["pagination"]["total"] == 3

    @patch("app.api.endpoints.user.UserService")
    def test_list_users_with_pagination(
        self, mock_user_service_class, client, mock_token_data, mock_users
    ):
        """Test users listing with pagination."""
        mock_user_service = AsyncMock()
        mock_user_service.list_users.return_value = mock_users[:2]
        mock_user_service.count_users.return_value = 3
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.get("/list?page=1&size=2")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False

    @patch("app.api.endpoints.user.UserService")
    def test_list_users_invalid_page_number(
        self, mock_user_service_class, client, mock_token_data
    ):
        """Test users listing with invalid page number."""
        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.get("/list?page=0&size=10")

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False

    @patch("app.api.endpoints.user.UserService")
    def test_list_users_invalid_size(
        self, mock_user_service_class, client, mock_token_data
    ):
        """Test users listing with invalid size."""
        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.get("/list?page=1&size=101")

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False

    @patch("app.api.endpoints.user.UserService")
    def test_list_users_server_error(
        self, mock_user_service_class, client, mock_token_data
    ):
        """Test users listing with server error."""
        mock_user_service = AsyncMock()
        mock_user_service.list_users.side_effect = Exception("Database error")
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        # Use pytest.raises to expect the exception
        with pytest.raises(Exception) as exc_info:
            client.get("/list?page=1&size=10")

        # Verify it's the expected database error
        assert "Database error" in str(exc_info.value)


class TestDeleteUserEndpoint:
    """Test cases for delete user endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(create_test_app())

    @pytest.fixture
    def test_data_factory(self):
        """Test data factory fixture."""
        from tests.conftest import TestDataFactory

        return TestDataFactory()

    @pytest.fixture
    def mock_token_data(self, test_data_factory):
        """Create mock token data."""
        return TokenData(
            user_id=str(ObjectId()),
            email="admin@example.com",
            token_type="access",
            expires_at=datetime.now(UTC),
        )

    @patch("app.api.endpoints.user.UserService")
    def test_delete_user_success(
        self, mock_user_service_class, client, mock_token_data
    ):
        """Test successful user deletion."""
        user_id = str(ObjectId())
        mock_user_service = AsyncMock()
        mock_user_service.delete_user.return_value = True
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.delete(f"/{user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "User deleted successfully"
        assert data["data"]["deleted_user_id"] == user_id

    @patch("app.api.endpoints.user.UserService")
    def test_delete_user_not_found(
        self, mock_user_service_class, client, mock_token_data
    ):
        """Test user deletion when user not found."""
        user_id = str(ObjectId())
        mock_user_service = AsyncMock()
        mock_user_service.delete_user.return_value = False
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.delete(f"/{user_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_delete_user_invalid_user_id(self, client, mock_token_data):
        """Test user deletion with invalid user ID format."""
        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        response = client.delete("/invalid_id")

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "Invalid user ID format" in data["message"]

    @patch("app.api.endpoints.user.UserService")
    def test_delete_user_server_error(
        self, mock_user_service_class, client, mock_token_data
    ):
        """Test user deletion with server error."""
        user_id = str(ObjectId())
        mock_user_service = AsyncMock()
        mock_user_service.delete_user.side_effect = Exception("Database error")
        mock_user_service_class.return_value = mock_user_service

        # Override the dependency
        client.app.dependency_overrides[get_current_user_token] = (
            lambda: mock_token_data
        )

        # Use pytest.raises to expect the exception
        with pytest.raises(Exception) as exc_info:
            client.delete(f"/{user_id}")

        # Verify it's the expected database error
        assert "Database error" in str(exc_info.value)
