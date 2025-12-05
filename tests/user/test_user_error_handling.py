"""Test user error handling and edge cases."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.exceptions import ConflictException, NotFoundException
from app.main import app
from app.services.user_service import UserService


class TestUserAPIErrorHandling:
    """Test user API error handling."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_create_user_validation_error_response(self, client):
        """Test validation error response format."""
        response = client.post(
            "/api/user/",
            json={
                "email": "invalid-email",
                "phone": "",
                "password": "short",
            },
        )

        assert response.status_code == 422
        data = response.json()

        # Verify response structure
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert data["message"] == "Validation failed"
        assert "timestamp" in data
        assert "validation_errors" in data
        assert isinstance(data["validation_errors"], list)
        assert len(data["validation_errors"]) > 0

        # Verify validation error details
        validation_errors = data["validation_errors"]
        assert any(error["field"] == "body.email" for error in validation_errors)
        assert any(
            "Phone number cannot be empty" in error["message"]
            for error in validation_errors
        )

    def test_create_user_email_conflict_error(self, client):
        """Test email conflict error response."""
        with patch("app.api.endpoints.user.UserService") as mock_service:
            mock_service.return_value.create_user = AsyncMock(
                side_effect=ConflictException(
                    message="User with this email already exists",
                    details={"email": "test@example.com"},
                )
            )

            response = client.post(
                "/api/user/",
                json={
                    "email": "test@example.com",
                    "phone": "+1234567890",
                    "password": "password123",
                },
            )

            assert response.status_code == 409
            data = response.json()

            # Verify error response structure
            assert data["success"] is False
            assert data["error_code"] == "CONFLICT"
            assert "User with this email already exists" in data["message"]
            assert data["details"]["email"] == "test@example.com"

    def test_get_user_not_found_error(self, client):
        """Test user not found error response."""
        with (
            patch(
                "app.core.auth_dependencies.verify_access_token"
            ) as mock_verify_token,
            patch(
                "app.core.auth_dependencies.verify_token_not_blocked"
            ) as mock_verify_not_blocked,
            patch("app.api.endpoints.user.UserService") as mock_service,
        ):
            # Mock JWT verification to return valid token data
            mock_verify_token.return_value = {
                "sub": "507f1f77bcf86cd799439011",
                "email": "test@example.com",
                "type": "access",
                "exp": int(datetime.now(UTC).timestamp()) + 3600,
            }
            mock_verify_not_blocked.return_value = True

            mock_service.return_value.get_user_by_id = AsyncMock(return_value=None)

            response = client.get(
                "/api/user/me", headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 404
            data = response.json()

            # Verify error response structure
            assert data["success"] is False
            assert data["error_code"] == "NOT_FOUND"
            assert "User not found" in data["message"]

    def test_update_user_not_found_error(self, client):
        """Test user update not found error response."""
        with (
            patch(
                "app.core.auth_dependencies.verify_access_token"
            ) as mock_verify_token,
            patch(
                "app.core.auth_dependencies.verify_token_not_blocked"
            ) as mock_verify_not_blocked,
            patch("app.api.endpoints.user.UserService") as mock_service,
        ):
            # Mock JWT verification to return valid token data
            mock_verify_token.return_value = {
                "sub": "507f1f77bcf86cd799439011",
                "email": "test@example.com",
                "type": "access",
                "exp": int(datetime.now(UTC).timestamp()) + 3600,
            }
            mock_verify_not_blocked.return_value = True

            mock_service.return_value.get_user_by_id = AsyncMock(return_value=None)

            response = client.put(
                "/api/user/me",
                json={"firstName": "John"},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 404
            data = response.json()

            # Verify error response structure
            assert data["success"] is False
            assert data["error_code"] == "NOT_FOUND"
            assert "User not found" in data["message"]

    def test_delete_user_not_found_error(self, client):
        """Test user deletion not found error response."""
        with (
            patch(
                "app.core.auth_dependencies.verify_access_token"
            ) as mock_verify_token,
            patch(
                "app.core.auth_dependencies.verify_token_not_blocked"
            ) as mock_verify_not_blocked,
            patch("app.api.endpoints.user.UserService") as mock_service,
        ):
            # Mock JWT verification to return valid token data
            mock_verify_token.return_value = {
                "sub": "507f1f77bcf86cd799439011",
                "email": "test@example.com",
                "type": "access",
                "exp": int(datetime.now(UTC).timestamp()) + 3600,
            }
            mock_verify_not_blocked.return_value = True

            mock_service.return_value.delete_user = AsyncMock(
                side_effect=NotFoundException("User not found")
            )

            response = client.delete(
                "/api/user/507f1f77bcf86cd799439011",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 404
            data = response.json()

            # Verify error response structure
            assert data["success"] is False
            assert data["error_code"] == "NOT_FOUND"
            assert "User not found" in data["message"]

    # def test_unauthorized_error(self, client):
    #     """Test unauthorized error response."""
    #     with patch('app.api.endpoints.user.get_current_user') as mock_get_user:
    #         mock_get_user.side_effect = UnauthorizedException("Authentication required")

    #         response = client.get("/api/user/me")

    #         assert response.status_code == 401
    #         data = response.json()

    #         # Verify error response structure
    #         assert data["success"] is False
    #         assert data["error_code"] == "UNAUTHORIZED"
    #         assert "Authentication required" in data["message"]

    def test_internal_server_error(self, client):
        """Test internal server error response."""
        with patch("app.api.endpoints.user.UserService") as mock_service:
            mock_service.return_value.create_user = AsyncMock(
                side_effect=Exception("Unexpected error")
            )

            # Use pytest.raises to catch the exception that will be raised
            with pytest.raises(Exception, match="Unexpected error"):
                client.post(
                    "/api/user/",
                    json={
                        "email": "test@example.com",
                        "phone": "+1234567890",
                        "password": "password123",
                    },
                )

    def test_validation_error_field_mapping(self, client):
        """Test that validation errors are properly mapped to fields."""
        response = client.post(
            "/api/user/",
            json={
                "email": "invalid-email",
                "phone": "",
                "password": "short",
            },
        )

        assert response.status_code == 422
        data = response.json()

        validation_errors = data["validation_errors"]
        field_names = [error["field"] for error in validation_errors]

        # Verify that all expected fields have validation errors
        assert "body.email" in field_names
        assert "body.phone" in field_names
        assert "body.password" in field_names
        # verifyByGovId field no longer exists

    def test_validation_error_message_clarity(self, client):
        """Test that validation error messages are clear and helpful."""
        response = client.post(
            "/api/user/",
            json={
                "email": "invalid-email",
                "phone": "",
                "password": "short",
            },
        )

        assert response.status_code == 422
        data = response.json()

        validation_errors = data["validation_errors"]
        messages = [error["message"] for error in validation_errors]

        # Verify that error messages are clear
        assert any("Phone number cannot be empty" in msg for msg in messages)
        assert any(
            "String should have at least 8 characters" in msg for msg in messages
        )
        # Boolean validation no longer needed for verifyByGovId

    def test_error_response_timestamp_format(self, client):
        """Test that error response timestamps are properly formatted."""
        response = client.post(
            "/api/user/",
            json={
                "email": "invalid-email",
                "phone": "",
                "password": "short",
            },
        )

        assert response.status_code == 422
        data = response.json()

        # Verify timestamp format
        assert "timestamp" in data
        timestamp = data["timestamp"]
        assert isinstance(timestamp, str)
        assert timestamp.endswith("Z")  # Should be in UTC format
        assert "T" in timestamp  # Should be in ISO format

    def test_error_response_data_field(self, client):
        """Test that error responses have data field set to null."""
        response = client.post(
            "/api/user/",
            json={
                "email": "invalid-email",
                "phone": "",
                "password": "short",
            },
        )

        assert response.status_code == 422
        data = response.json()

        # Verify data field is null for errors
        assert data["data"] is None

    def test_success_response_data_field(self, client):
        """Test that success responses have data field populated."""
        with patch("app.api.endpoints.user.UserService") as mock_service:
            from app.models.user import UserInDB, UserType

            mock_service.return_value.create_user = AsyncMock(
                return_value=UserInDB(
                    id=ObjectId(),
                    email="test@example.com",
                    phone="+1234567890",
                    password="hashed_password",
                    userType=UserType.USER,
                    features=[],
                    isActive=True,
                    isVerified=False,
                    createdAt=datetime.now(UTC),
                    updatedAt=datetime.now(UTC),
                )
            )

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
                response = client.post(
                    "/api/user/",
                    json={
                        "email": "test@example.com",
                        "phone": "+1234567890",
                        "password": "password123",
                    },
                )

            assert response.status_code == 200
            data = response.json()

            # Verify data field is populated for success
            assert data["data"] is not None
            assert data["data"]["email"] == "test@example.com"


class TestUserServiceErrorHandling:
    """Test user service error handling."""

    @pytest.fixture
    def mock_db(self):
        """Mock database for testing."""
        db = MagicMock()
        db.users = MagicMock()
        db.users.find_one = AsyncMock()
        db.users.insert_one = AsyncMock()
        db.users.update_one = AsyncMock()
        db.users.delete_one = AsyncMock()
        db.users.count_documents = AsyncMock()
        return db

    @pytest.fixture
    def user_service(self, mock_db):
        """Create UserService instance with mocked database."""
        return UserService(mock_db)

    @pytest.mark.asyncio
    async def test_create_user_database_error(self, user_service):
        """Test user creation with database error."""
        # Mock Beanie User model
        with patch("app.services.user_service.User") as mock_user_class:
            mock_user_class.find_one = AsyncMock(return_value=None)
            mock_user_class.return_value.insert = AsyncMock(
                side_effect=Exception("Database connection failed")
            )

            from app.models.user import UserCreate

            user_create = UserCreate(
                email="test@example.com",
                phone="+1234567890",
                password="password123",
            )

            with pytest.raises(Exception, match="Database connection failed"):
                await user_service.create_user(user_create)

    @pytest.mark.asyncio
    async def test_get_user_database_error(self, user_service):
        """Test user retrieval with database error."""
        # Mock Beanie User model
        with patch("app.services.user_service.User") as mock_user_class:
            mock_user_class.find_one = AsyncMock(
                side_effect=Exception("Database connection failed")
            )

            with pytest.raises(Exception, match="Database connection failed"):
                await user_service.get_user_by_id("507f1f77bcf86cd799439011")

    @pytest.mark.asyncio
    async def test_update_user_database_error(self, user_service):
        """Test user update with database error."""
        # Mock Beanie User model
        with patch("app.services.user_service.User") as mock_user_class:
            mock_user = MagicMock()
            mock_user.id = ObjectId()
            mock_user.save = AsyncMock(
                side_effect=Exception("Database connection failed")
            )
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            from app.models.user import UserUpdate

            user_update = UserUpdate(firstName="John")

            with pytest.raises(Exception, match="Database connection failed"):
                await user_service.update_user("507f1f77bcf86cd799439011", user_update)

    @pytest.mark.asyncio
    async def test_delete_user_database_error(self, user_service):
        """Test user deletion with database error."""
        # Mock Beanie User model
        with patch("app.services.user_service.User") as mock_user_class:
            mock_user = MagicMock()
            mock_user.id = ObjectId()
            mock_user.delete = AsyncMock(
                side_effect=Exception("Database connection failed")
            )
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            with pytest.raises(Exception, match="Database connection failed"):
                await user_service.delete_user("507f1f77bcf86cd799439011")

    @pytest.mark.asyncio
    async def test_list_users_database_error(self, user_service):
        """Test user listing with database error."""
        # Mock Beanie User model
        with patch("app.services.user_service.User") as mock_user_class:
            mock_user_class.find = MagicMock()
            mock_user_class.find.return_value.skip.return_value.limit.return_value.to_list = AsyncMock(
                side_effect=Exception("Database connection failed")
            )

            with pytest.raises(Exception, match="Database connection failed"):
                await user_service.list_users(skip=0, limit=10)

    @pytest.mark.asyncio
    async def test_count_users_database_error(self, user_service):
        """Test user counting with database error."""
        # Mock Beanie User model
        with patch("app.services.user_service.User") as mock_user_class:
            mock_user_class.count = AsyncMock(
                side_effect=Exception("Database connection failed")
            )

            with pytest.raises(Exception, match="Database connection failed"):
                await user_service.count_users()


class TestUserValidationErrorHandling:
    """Test user validation error handling."""

    def test_phone_validation_error_messages(self):
        """Test phone validation error messages."""
        from app.utils.validators import (
            validate_phone_number,
            validate_required_phone_number,
        )

        # Test required phone validation errors
        with pytest.raises(ValueError, match="Phone number is required"):
            validate_required_phone_number(None)

        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_required_phone_number("")

        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("123")

        # Test optional phone validation errors
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_phone_number("")

    def test_email_validation_error_messages(self):
        """Test email validation error messages."""
        from app.schemas.user import UserCreateRequest

        with pytest.raises(ValueError) as exc_info:
            UserCreateRequest(
                email="invalid-email",
                phone="+1234567890",
                password="password123",
            )

        # Verify that email validation error is raised
        assert "email" in str(exc_info.value)

    def test_password_validation_error_messages(self):
        """Test password validation error messages."""
        from app.schemas.user import UserCreateRequest

        with pytest.raises(ValueError) as exc_info:
            UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password="short",
            )

        # Verify that password validation error is raised
        assert "password" in str(exc_info.value)

    def test_boolean_validation_error_messages(self):
        """Test boolean validation error messages."""
        # verifyByGovId field no longer exists, so this test is no longer applicable
        # Instead, test userType validation
        from app.models.user import UserType
        from app.schemas.user import UserCreateRequest

        # Valid userType
        request = UserCreateRequest(
            email="test@example.com",
            phone="+1234567890",
            password="password123",
            userType=UserType.USER,
        )
        assert request.userType == UserType.USER


class TestUserEdgeCases:
    """Test user edge cases and boundary conditions."""

    def test_very_long_email(self):
        """Test very long email handling."""
        from app.schemas.user import UserCreateRequest

        # Very long email (should be handled by email validator)
        long_email = "a" * 1000 + "@example.com"

        with pytest.raises(ValueError):
            UserCreateRequest(
                email=long_email,
                phone="+1234567890",
                password="password123",
            )

    def test_very_long_password(self):
        """Test very long password handling."""
        from app.schemas.user import UserCreateRequest

        # Very long password (should be rejected by length validation)
        long_password = "a" * 101

        with pytest.raises(ValueError):
            UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password=long_password,
            )

    def test_unicode_characters_in_fields(self):
        """Test unicode characters in various fields."""
        from app.schemas.user import UserCreateRequest, UserUpdateRequest

        # Test unicode in user creation
        request = UserCreateRequest(
            email="tëst@ëxämplë.com",
            phone="+1234567890",
            password="password123",
        )
        assert request.email == "tëst@ëxämplë.com"

        # Test unicode in user update
        update_request = UserUpdateRequest(
            firstName="José", lastName="García", pinCode="12345"
        )
        assert update_request.firstName == "José"
        assert update_request.lastName == "García"

    def test_special_characters_in_phone(self):
        """Test special characters in phone number."""
        from app.utils.validators import validate_required_phone_number

        # Test various special characters
        test_cases = [
            ("+1-234-567-890", "+1234567890"),
            ("+1 (234) 567-890", "+1234567890"),
            ("+1.234.567.890", "+1234567890"),
            ("+1 234 567 890", "+1234567890"),
        ]

        for input_phone, expected in test_cases:
            assert validate_required_phone_number(input_phone) == expected

    def test_boundary_phone_lengths(self):
        """Test boundary phone number lengths."""
        from app.utils.validators import validate_required_phone_number

        # Test minimum valid length
        assert validate_required_phone_number("1234567") == "+1234567"

        # Test maximum valid length
        assert validate_required_phone_number("123456789012345") == "+123456789012345"

        # Test just below minimum
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("123456")

        # Test just above maximum
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("1234567890123456")

    def test_empty_string_vs_none_handling(self):
        """Test proper handling of empty strings vs None."""
        from app.schemas.user import UserUpdateRequest

        # None should be allowed for optional fields
        request = UserUpdateRequest(firstName=None)
        assert request.firstName is None

        # Empty string should be allowed for optional fields (if not validated)
        request = UserUpdateRequest(firstName="")
        assert request.firstName == ""

        # But phone should be validated even in updates
        with pytest.raises(ValueError):
            UserUpdateRequest(phone="")

    def test_boolean_edge_cases(self):
        """Test userType field edge cases (replaces boolean field testing)."""
        from pydantic import ValidationError

        from app.models.user import UserType
        from app.schemas.user import UserCreateRequest

        # Test valid userType values (only USER and ORG_USER allowed for self-registration)
        valid_test_cases = [
            (UserType.USER, UserType.USER),
            (UserType.ORG_USER, UserType.ORG_USER),
            ("user", UserType.USER),
            ("org_user", UserType.ORG_USER),
        ]

        for input_value, expected in valid_test_cases:
            request = UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password="password123",
                userType=input_value,
            )
            assert request.userType == expected

        # Test that elevated roles (ADMIN, ORG_ADMIN) are rejected for self-registration
        elevated_roles = [UserType.ADMIN, UserType.ORG_ADMIN, "admin", "org_admin"]
        for elevated_role in elevated_roles:
            with pytest.raises(ValidationError) as exc_info:
                UserCreateRequest(
                    email="test@example.com",
                    phone="+1234567890",
                    password="password123",
                    userType=elevated_role,
                )
            # Verify the error message mentions self-assignment restriction
            error_str = str(exc_info.value)
            assert (
                "cannot be self-assigned" in error_str
                or "self-assigned" in error_str.lower()
            )

        # Test invalid userType values (not a valid enum value)
        with pytest.raises(ValidationError):
            UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password="password123",
                userType="invalid_type",  # Invalid user type
            )
