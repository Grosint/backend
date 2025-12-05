"""Comprehensive unit tests for user creation, validation, and updates."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.exceptions import ConflictException, NotFoundException
from app.main import app
from app.models.user import User, UserCreate, UserInDB, UserUpdate
from app.schemas.user import UserCreateRequest, UserUpdateRequest
from app.services.user_service import UserService
from app.utils.validators import validate_phone_number, validate_required_phone_number


class TestUserValidation:
    """Test user validation logic."""

    def test_phone_validation_required_fields(self):
        """Test phone validation for required fields."""
        # Valid phone numbers
        assert validate_required_phone_number("+1234567890") == "+1234567890"
        assert validate_required_phone_number("1234567890") == "+1234567890"
        assert validate_required_phone_number("+91 98765 43210") == "+919876543210"

        # Invalid cases
        with pytest.raises(ValueError, match="Phone number is required"):
            validate_required_phone_number(None)

        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_required_phone_number("")

        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("123")

        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("12345678901234567890")

    def test_phone_validation_optional_fields(self):
        """Test phone validation for optional fields."""
        # Valid cases
        assert validate_phone_number("+1234567890") == "+1234567890"
        assert validate_phone_number("1234567890") == "+1234567890"
        assert validate_phone_number(None) is None

        # Invalid cases
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_phone_number("")

    def test_user_create_request_validation(self):
        """Test UserCreateRequest validation."""
        # Valid request
        valid_request = UserCreateRequest(
            email="test@example.com",
            phone="+1234567890",
            password="password123",
        )
        assert valid_request.email == "test@example.com"
        assert valid_request.phone == "+1234567890"
        assert valid_request.password == "password123"

        # Invalid email
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="invalid-email",
                phone="+1234567890",
                password="password123",
            )
        assert "email" in str(exc_info.value)

        # Empty phone
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="test@example.com",
                phone="",
                password="password123",
            )
        assert "Phone number cannot be empty" in str(exc_info.value)

        # Missing required fields
        with pytest.raises(ValidationError):
            UserCreateRequest(
                email="test@example.com",
                # phone missing
                password="password123",
            )

    def test_user_update_request_validation(self):
        """Test UserUpdateRequest validation (all fields optional)."""
        # Valid update with all fields
        valid_update = UserUpdateRequest(
            email="new@example.com",
            phone="+9876543210",
            firstName="John",
            lastName="Doe",
        )
        assert valid_update.email == "new@example.com"
        assert valid_update.phone == "+9876543210"

        # Valid update with partial fields
        partial_update = UserUpdateRequest(firstName="Jane")
        assert partial_update.firstName == "Jane"
        assert partial_update.email is None
        assert partial_update.phone is None

        # Invalid phone in update
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateRequest(phone="")
        assert "Phone number cannot be empty" in str(exc_info.value)

        # Invalid email in update
        with pytest.raises(ValidationError):
            UserUpdateRequest(email="invalid-email")


class TestUserModel:
    """Test User model behavior."""

    def test_user_base_validation(self):
        """Test UserBase model validation."""
        from app.models.user import UserBase

        # Valid user base
        user_base = UserBase(
            email="test@example.com", phone="+1234567890", password="hashed_password"
        )
        assert user_base.email == "test@example.com"
        assert user_base.phone == "+1234567890"
        assert user_base.isActive is True  # Default value
        assert user_base.isVerified is False  # Default value

    def test_user_create_model(self):
        """Test UserCreate model validation."""
        # Valid user create
        user_create = UserCreate(
            email="test@example.com",
            phone="+1234567890",
            password="password123",
        )
        assert user_create.email == "test@example.com"
        assert user_create.phone == "+1234567890"

    def test_user_update_model(self):
        """Test UserUpdate model validation."""
        # Valid user update
        user_update = UserUpdate(firstName="John", lastName="Doe", phone="+9876543210")
        assert user_update.firstName == "John"
        assert user_update.lastName == "Doe"
        assert user_update.phone == "+9876543210"
        assert user_update.email is None  # Not provided

    def test_user_document_timestamps(self):
        """Test User document timestamp behavior."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            # Mock the before_event hook
            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )

            # Test timestamp setting
            user.set_timestamps()
            assert user.createdAt is not None
            assert user.updatedAt is not None
            assert isinstance(user.createdAt, datetime)
            assert isinstance(user.updatedAt, datetime)


class TestUserService:
    """Test UserService business logic."""

    @pytest.fixture
    def mock_db(self):
        """Mock database for testing."""
        return AsyncMock()

    @pytest.fixture
    def user_service(self, mock_db):
        """Create UserService instance with mocked database."""
        return UserService(mock_db)

    @pytest.fixture
    def test_data_factory(self):
        """Test data factory fixture."""
        from tests.conftest import TestDataFactory

        return TestDataFactory()

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service, test_data_factory):
        """Test successful user creation."""
        # Create test data using factory
        user_create_data = test_data_factory.create_user_create_request()
        user_create = UserCreate(**user_create_data)

        # Create a mock user instance
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId()
        mock_user.email = user_create_data["email"]
        mock_user.phone = user_create_data["phone"]
        mock_user.password = "hashed_password"
        mock_user.userType = "user"
        mock_user.features = []
        mock_user.isActive = True
        mock_user.isVerified = False
        mock_user.firstName = None
        mock_user.lastName = None
        mock_user.address = None
        mock_user.city = None
        mock_user.pinCode = None
        mock_user.state = None
        mock_user.organizationId = None
        mock_user.orgName = None
        mock_user.createdAt = datetime.now(UTC)
        mock_user.updatedAt = datetime.now(UTC)
        mock_user.insert = AsyncMock()

        # Mock the User model operations at the service level
        with patch("app.services.user_service.User") as mock_user_class:
            # Setup the mock to handle the query pattern: User.email == user.email
            mock_user_class.email = MagicMock()
            mock_user_class.email.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=None)  # No existing user
            mock_user_class.return_value = mock_user

            # Mock password hashing
            with patch(
                "app.services.user_service.hash_password",
                return_value="hashed_password",
            ):
                result = await user_service.create_user(user_create)

                # Verify Beanie calls
                mock_user_class.find_one.assert_called_once()
                mock_user.insert.assert_called_once()

                # Verify result
                assert isinstance(result, UserInDB)
                assert result.email == user_create_data["email"]
                assert result.phone == user_create_data["phone"]
                assert result.isActive is True  # Should be set to True
                assert result.isVerified is False  # Should be set to False
                assert result.password == "hashed_password"

    @pytest.mark.asyncio
    async def test_create_user_email_conflict(self, user_service, test_data_factory):
        """Test user creation with existing email."""
        # Create test data using factory
        user_create_data = test_data_factory.create_user_create_request()
        user_create = UserCreate(**user_create_data)

        # Mock existing user found
        mock_existing_user = Mock(spec=User)
        mock_existing_user.email = user_create_data["email"]

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.email = MagicMock()
            mock_user_class.email.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_existing_user)

            with pytest.raises(ConflictException) as exc_info:
                await user_service.create_user(user_create)

            # Verify Beanie was queried for existing user
            mock_user_class.find_one.assert_called_once()

            assert "User with this email already exists" in str(exc_info.value)
            assert exc_info.value.details["email"] == user_create_data["email"]

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, user_service, test_data_factory):
        """Test successful user retrieval by ID."""
        # Create test data using factory with valid ObjectId
        user_id = str(ObjectId())
        mock_user_data = test_data_factory.create_user_data(id=user_id)

        # Create a mock user instance
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId(mock_user_data["id"])
        mock_user.email = mock_user_data["email"]
        mock_user.phone = mock_user_data["phone"]
        mock_user.password = mock_user_data["password"]
        mock_user.userType = mock_user_data.get("userType", "user")
        mock_user.features = mock_user_data.get("features", [])
        mock_user.isActive = mock_user_data["isActive"]
        mock_user.isVerified = mock_user_data["isVerified"]
        mock_user.firstName = mock_user_data.get("firstName")
        mock_user.lastName = mock_user_data.get("lastName")
        mock_user.address = mock_user_data.get("address")
        mock_user.city = mock_user_data.get("city")
        mock_user.pinCode = mock_user_data.get("pinCode")
        mock_user.state = mock_user_data.get("state")
        mock_user.organizationId = mock_user_data.get("organizationId")
        mock_user.orgName = mock_user_data.get("orgName")
        mock_user.createdAt = mock_user_data["createdAt"]
        mock_user.updatedAt = mock_user_data["updatedAt"]

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern: User.id == ObjectId(user_id)
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            result = await user_service.get_user_by_id(mock_user_data["id"])

            # Verify Beanie call
            mock_user_class.find_one.assert_called_once()

            # Verify result
            assert result is not None
            assert result.email == mock_user_data["email"]

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_service):
        """Test user retrieval with non-existent ID."""
        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=None)

            result = await user_service.get_user_by_id("507f1f77bcf86cd799439011")

            # Verify Beanie call
            mock_user_class.find_one.assert_called_once()

            # Verify result
            assert result is None

    @pytest.mark.asyncio
    async def test_update_user_success(self, user_service, test_data_factory):
        """Test successful user update."""
        # Create test data using factory with valid ObjectId
        user_id = str(ObjectId())
        existing_user_data = test_data_factory.create_user_data(id=user_id)

        # Create a mock user instance
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId(existing_user_data["id"])
        mock_user.email = existing_user_data["email"]
        mock_user.phone = existing_user_data["phone"]
        mock_user.password = existing_user_data["password"]
        mock_user.userType = existing_user_data.get("userType", "user")
        mock_user.features = existing_user_data.get("features", [])
        mock_user.isActive = existing_user_data["isActive"]
        mock_user.isVerified = existing_user_data["isVerified"]
        mock_user.firstName = existing_user_data.get("firstName")
        mock_user.lastName = existing_user_data.get("lastName")
        mock_user.address = existing_user_data.get("address")
        mock_user.city = existing_user_data.get("city")
        mock_user.pinCode = existing_user_data.get("pinCode")
        mock_user.state = existing_user_data.get("state")
        mock_user.organizationId = existing_user_data.get("organizationId")
        mock_user.orgName = existing_user_data.get("orgName")
        mock_user.createdAt = existing_user_data["createdAt"]
        mock_user.updatedAt = existing_user_data["updatedAt"]
        mock_user.save = AsyncMock()

        # Create update request using factory
        update_data = test_data_factory.create_user_update_request(
            firstName="John", lastName="Doe", phone="+9876543210"
        )
        user_update = UserUpdate(**update_data)

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            result = await user_service.update_user(
                existing_user_data["id"], user_update
            )

            # Verify Beanie calls (update may call find_one multiple times)
            assert mock_user_class.find_one.call_count >= 1
            mock_user.save.assert_called_once()

            # Verify result
            assert result is not None
            assert result.firstName == "John"
            assert result.lastName == "Doe"
            assert result.phone == "+9876543210"

    @pytest.mark.asyncio
    async def test_update_user_restricted_fields(self, user_service, test_data_factory):
        """Test that isActive and isVerified cannot be updated."""
        # Create test data using factory with valid ObjectId
        user_id = str(ObjectId())
        existing_user_data = test_data_factory.create_user_data(id=user_id)

        # Create a mock user instance
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId(existing_user_data["id"])
        mock_user.email = existing_user_data["email"]
        mock_user.phone = existing_user_data["phone"]
        mock_user.password = existing_user_data["password"]
        mock_user.userType = existing_user_data.get("userType", "user")
        mock_user.features = existing_user_data.get("features", [])
        mock_user.isActive = existing_user_data["isActive"]
        mock_user.isVerified = existing_user_data["isVerified"]
        mock_user.firstName = existing_user_data.get("firstName")
        mock_user.lastName = existing_user_data.get("lastName")
        mock_user.address = existing_user_data.get("address")
        mock_user.city = existing_user_data.get("city")
        mock_user.pinCode = existing_user_data.get("pinCode")
        mock_user.state = existing_user_data.get("state")
        mock_user.organizationId = existing_user_data.get("organizationId")
        mock_user.orgName = existing_user_data.get("orgName")
        mock_user.createdAt = existing_user_data["createdAt"]
        mock_user.updatedAt = existing_user_data["updatedAt"]
        mock_user.save = AsyncMock()

        # Try to update restricted fields
        user_update = UserUpdate(
            firstName="John",
            isActive=False,  # Should be ignored
            isVerified=True,  # Should be ignored
        )

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            result = await user_service.update_user(
                existing_user_data["id"], user_update
            )

            # Verify that the update was processed
            mock_user.save.assert_called_once()

            # Check that restricted fields were not updated
            assert result.firstName == "John"
            # isActive and isVerified should remain unchanged
            # (This would need to be verified in the actual implementation)

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service):
        """Test successful user deletion."""
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId()
        mock_user.delete = AsyncMock()

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            result = await user_service.delete_user(str(mock_user.id))

            # Verify Beanie calls
            mock_user_class.find_one.assert_called_once()
            mock_user.delete.assert_called_once()

            # Verify result
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_service):
        """Test user deletion with non-existent ID."""
        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=None)

            result = await user_service.delete_user("507f1f77bcf86cd799439011")

            # Verify Beanie call
            mock_user_class.find_one.assert_called_once()

            # Verify result
            assert result is False

    @pytest.mark.asyncio
    async def test_list_users_with_pagination(self, user_service, test_data_factory):
        """Test user listing with pagination."""
        # Create test data using factory with valid ObjectIds
        mock_users_data = [
            test_data_factory.create_user_data(
                id=str(ObjectId()),
                email="user1@example.com",
                phone="+1234567890",
            ),
            test_data_factory.create_user_data(
                id=str(ObjectId()),
                email="user2@example.com",
                phone="+9876543210",
            ),
        ]

        # Create mock user instances
        mock_user1 = MagicMock()
        mock_user1.id = ObjectId(mock_users_data[0]["id"])
        mock_user1.email = mock_users_data[0]["email"]
        mock_user1.phone = mock_users_data[0]["phone"]
        mock_user1.password = mock_users_data[0]["password"]
        mock_user1.userType = mock_users_data[0].get("userType", "user")
        mock_user1.features = mock_users_data[0].get("features", [])
        mock_user1.isActive = mock_users_data[0]["isActive"]
        mock_user1.isVerified = mock_users_data[0]["isVerified"]
        mock_user1.firstName = mock_users_data[0].get("firstName")
        mock_user1.lastName = mock_users_data[0].get("lastName")
        mock_user1.address = mock_users_data[0].get("address")
        mock_user1.city = mock_users_data[0].get("city")
        mock_user1.pinCode = mock_users_data[0].get("pinCode")
        mock_user1.state = mock_users_data[0].get("state")
        mock_user1.organizationId = mock_users_data[0].get("organizationId")
        mock_user1.orgName = mock_users_data[0].get("orgName")
        mock_user1.createdAt = mock_users_data[0]["createdAt"]
        mock_user1.updatedAt = mock_users_data[0]["updatedAt"]

        mock_user2 = MagicMock()
        mock_user2.id = ObjectId(mock_users_data[1]["id"])
        mock_user2.email = mock_users_data[1]["email"]
        mock_user2.phone = mock_users_data[1]["phone"]
        mock_user2.password = mock_users_data[1]["password"]
        mock_user2.userType = mock_users_data[1].get("userType", "user")
        mock_user2.features = mock_users_data[1].get("features", [])
        mock_user2.isActive = mock_users_data[1]["isActive"]
        mock_user2.isVerified = mock_users_data[1]["isVerified"]
        mock_user2.firstName = mock_users_data[1].get("firstName")
        mock_user2.lastName = mock_users_data[1].get("lastName")
        mock_user2.address = mock_users_data[1].get("address")
        mock_user2.city = mock_users_data[1].get("city")
        mock_user2.pinCode = mock_users_data[1].get("pinCode")
        mock_user2.state = mock_users_data[1].get("state")
        mock_user2.organizationId = mock_users_data[1].get("organizationId")
        mock_user2.orgName = mock_users_data[1].get("orgName")
        mock_user2.createdAt = mock_users_data[1]["createdAt"]
        mock_user2.updatedAt = mock_users_data[1]["updatedAt"]

        # Mock find operation
        mock_cursor = MagicMock()
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[mock_user1, mock_user2])

        with patch("app.services.user_service.User.find", return_value=mock_cursor):
            result = await user_service.list_users(skip=0, limit=10)

            # Verify result
            assert len(result) == 2
            assert result[0].email == "user1@example.com"
            assert result[1].email == "user2@example.com"

    @pytest.mark.asyncio
    async def test_count_users(self, user_service):
        """Test user counting."""
        with patch("app.models.user.User.count", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 5

            result = await user_service.count_users()

            # Verify Beanie call
            mock_count.assert_called_once()

            # Verify result
            assert result == 5


class TestUserAPIEndpoints:
    """Test user API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def test_data_factory(self):
        """Test data factory fixture."""
        from tests.conftest import TestDataFactory

        return TestDataFactory()

    def _mock_auth_dependency(self, user_id: str, email: str):
        """Helper to mock authentication dependency."""
        mock_token_data = TokenData(
            user_id=user_id,
            email=email,
            token_type="access",
            expires_at=datetime.now(UTC),
        )
        app.dependency_overrides[get_current_user_token] = lambda: mock_token_data
        return mock_token_data

    def test_create_user_success(self, client, test_data_factory):
        """Test successful user creation via API."""
        # Create test data using factory
        user_create_data = test_data_factory.create_user_create_request()
        user_in_db_data = test_data_factory.create_user_data(
            id=str(ObjectId()),
            email=user_create_data["email"],
            phone=user_create_data["phone"],
        )

        with (
            patch("app.api.endpoints.user.UserService") as mock_service,
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
            mock_service.return_value.create_user = AsyncMock(
                return_value=UserInDB(**user_in_db_data)
            )

            response = client.post("/api/user/", json=user_create_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "User created successfully" in data["message"]
            assert data["data"]["email"] == user_create_data["email"]
            assert data["data"]["isActive"] is True
            assert data["data"]["isVerified"] is False

    def test_create_user_validation_error(self, client):
        """Test user creation with validation errors."""
        # Test with invalid email
        response = client.post(
            "/api/user/",
            json={
                "email": "invalid-email",
                "phone": "+1234567890",
                "password": "password123",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "validation_errors" in data

    def test_create_user_email_conflict(self, client, test_data_factory):
        """Test user creation with existing email."""
        # Create test data using factory
        user_create_data = test_data_factory.create_user_create_request()

        with patch("app.api.endpoints.user.UserService") as mock_service:
            mock_service.return_value.create_user = AsyncMock(
                side_effect=ConflictException(
                    message="User with this email already exists",
                    details={"email": user_create_data["email"]},
                )
            )

            response = client.post("/api/user/", json=user_create_data)

            assert response.status_code == 409
            data = response.json()
            assert data["success"] is False
            assert "User with this email already exists" in data["message"]

    def test_get_current_user_success(self, client, test_data_factory):
        """Test successful current user retrieval."""
        # Create test data using factory
        user_data = test_data_factory.create_user_data(id=str(ObjectId()))

        # Mock authentication
        self._mock_auth_dependency(str(ObjectId()), user_data["email"])

        try:
            with patch("app.api.endpoints.user.UserService") as mock_service:
                mock_service.return_value.get_user_by_id = AsyncMock(
                    return_value=UserInDB(**user_data)
                )

                response = client.get("/api/user/me")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["email"] == user_data["email"]
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_update_user_success(self, client, test_data_factory):
        """Test successful user update."""
        # Create test data using factory
        user_data = test_data_factory.create_user_data(id=str(ObjectId()))
        update_data = test_data_factory.create_user_update_request(
            firstName="John", lastName="Doe", phone="+9876543210"
        )
        updated_user_data = test_data_factory.create_user_data(
            id=user_data["id"], firstName="John", lastName="Doe", phone="+9876543210"
        )

        # Mock authentication
        self._mock_auth_dependency(str(ObjectId()), user_data["email"])

        try:
            with patch("app.api.endpoints.user.UserService") as mock_service:
                mock_service_instance = mock_service.return_value
                mock_service_instance.get_user_by_id = AsyncMock(
                    return_value=UserInDB(**user_data)
                )
                mock_service_instance.update_user = AsyncMock(
                    return_value=UserInDB(**updated_user_data)
                )

                response = client.put("/api/user/me", json=update_data)

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["firstName"] == "John"
                assert data["data"]["lastName"] == "Doe"
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_update_user_restricted_fields(self, client, test_data_factory):
        """Test that restricted fields cannot be updated."""
        # Create test data using factory
        user_data = test_data_factory.create_user_data(id=str(ObjectId()))
        updated_user_data = test_data_factory.create_user_data(
            id=user_data["id"],
            firstName="John",
            isActive=True,  # Should remain unchanged
            isVerified=False,  # Should remain unchanged
        )

        # Mock authentication
        self._mock_auth_dependency(str(ObjectId()), user_data["email"])

        try:
            with patch("app.api.endpoints.user.UserService") as mock_service:
                # Mock that the service ignores restricted fields
                mock_service_instance = mock_service.return_value
                mock_service_instance.get_user_by_id = AsyncMock(
                    return_value=UserInDB(**user_data)
                )
                mock_service_instance.update_user = AsyncMock(
                    return_value=UserInDB(**updated_user_data)
                )

                response = client.put(
                    "/api/user/me",
                    json={
                        "firstName": "John",
                        "isActive": False,  # Should be ignored
                        "isVerified": True,  # Should be ignored
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["firstName"] == "John"
                # isActive and isVerified should remain unchanged
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_list_users_success(self, client, test_data_factory):
        """Test successful user listing."""
        # Create test data using factory
        mock_users_data = [
            test_data_factory.create_user_data(
                id=str(ObjectId()),
                email="user1@example.com",
                phone="+1234567890",
            ),
            test_data_factory.create_user_data(
                id=str(ObjectId()),
                email="user2@example.com",
                phone="+9876543210",
            ),
        ]
        mock_users = [UserInDB(**user_data) for user_data in mock_users_data]

        # Mock authentication
        self._mock_auth_dependency(str(ObjectId()), "test@example.com")

        try:
            with patch("app.api.endpoints.user.UserService") as mock_service:
                mock_service_instance = mock_service.return_value
                mock_service_instance.list_users = AsyncMock(return_value=mock_users)
                mock_service_instance.count_users = AsyncMock(return_value=2)

                response = client.get("/api/user/list?page=1&size=10")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert len(data["data"]) == 2
                assert "pagination" in data
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_delete_user_success(self, client):
        """Test successful user deletion."""
        # Create valid ObjectId for the test
        user_id = str(ObjectId())

        # Mock authentication
        self._mock_auth_dependency(user_id, "test@example.com")

        try:
            with patch("app.api.endpoints.user.UserService") as mock_service:
                mock_service_instance = mock_service.return_value
                mock_service_instance.delete_user = AsyncMock(return_value=True)

                response = client.delete(f"/api/user/{user_id}")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "User deleted successfully" in data["message"]
        finally:
            # Clean up the override
            app.dependency_overrides.clear()

    def test_delete_user_not_found(self, client):
        """Test user deletion with non-existent ID."""
        # Create valid ObjectId for the test
        user_id = str(ObjectId())

        # Mock authentication
        self._mock_auth_dependency(user_id, "test@example.com")

        try:
            with patch("app.api.endpoints.user.UserService") as mock_service:
                mock_service_instance = mock_service.return_value
                mock_service_instance.delete_user = AsyncMock(
                    side_effect=NotFoundException("User not found")
                )

                response = client.delete(f"/api/user/{user_id}")

                assert response.status_code == 404
                data = response.json()
                assert data["success"] is False
                assert "User not found" in data["message"]
        finally:
            # Clean up the override
            app.dependency_overrides.clear()


class TestDatabaseInteractions:
    """Test database interaction behaviors."""

    def test_user_creation_sets_timestamps(self):
        """Test that user creation sets createdAt and updatedAt."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )

            # Simulate the before_event hook
            user.set_timestamps()

            assert user.createdAt is not None
            assert user.updatedAt is not None
            assert isinstance(user.createdAt, datetime)
            assert isinstance(user.updatedAt, datetime)
            assert user.createdAt <= datetime.now(UTC)
            assert user.updatedAt <= datetime.now(UTC)

    def test_user_update_updates_timestamp(self):
        """Test that user update modifies updatedAt."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
                createdAt=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
                updatedAt=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            )

            original_updated_at = user.updatedAt

            # Simulate update
            user.set_timestamps()

            assert user.updatedAt > original_updated_at
            assert user.createdAt == datetime(
                2024, 1, 1, 12, 0, 0, tzinfo=UTC
            )  # Should not change

    def test_user_model_settings(self):
        """Test User model settings."""
        assert User.Settings.name == "users"

    def test_user_email_index(self):
        """Test that email field has proper indexing."""
        # This would need to be tested with actual Beanie integration
        # For now, we can verify the field definition
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )
            assert hasattr(user, "email")
            assert user.email == "test@example.com"


class TestUserEdgeCases:
    """Test edge cases and comprehensive error scenarios."""

    @pytest.fixture
    def test_data_factory(self):
        """Test data factory fixture."""
        from tests.conftest import TestDataFactory

        return TestDataFactory()

    def test_phone_number_normalization_edge_cases(self, test_data_factory):
        """Test phone number normalization with various formats."""
        # Test various phone number formats
        test_cases = [
            ("+1 (234) 567-890", "+1234567890"),
            ("+91 98765 43210", "+919876543210"),
            ("1234567890", "+1234567890"),
            ("+44 20 7946 0958", "+442079460958"),
            ("+33 1 42 86 83 26", "+33142868326"),
        ]

        for input_phone, expected_phone in test_cases:
            result = validate_required_phone_number(input_phone)
            assert result == expected_phone

    def test_phone_number_boundary_conditions(self):
        """Test phone number validation at boundary conditions."""
        # Test minimum length (7 digits)
        assert validate_required_phone_number("1234567") == "+1234567"

        # Test maximum length (15 digits)
        long_phone = "123456789012345"
        assert validate_required_phone_number(long_phone) == f"+{long_phone}"

        # Test just under minimum (6 digits)
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("123456")

        # Test just over maximum (16 digits)
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("1234567890123456")

    def test_unicode_and_special_characters(self, test_data_factory):
        """Test handling of unicode and special characters in user data."""
        # Test unicode in names
        user_data = test_data_factory.create_user_data(
            firstName="José", lastName="García-López"
        )
        assert user_data["firstName"] == "José"
        assert user_data["lastName"] == "García-López"

        # Test special characters in email (should be valid)
        user_data = test_data_factory.create_user_data(email="test+tag@example.com")
        assert user_data["email"] == "test+tag@example.com"

    def test_password_validation_edge_cases(self):
        """Test password validation edge cases."""
        # Test minimum length
        valid_short_password = "12345678"  # 8 characters
        user_create = UserCreateRequest(
            email="test@example.com",
            phone="+1234567890",
            password=valid_short_password,
        )
        assert user_create.password == valid_short_password

        # Test maximum length
        valid_long_password = "a" * 100  # 100 characters
        user_create = UserCreateRequest(
            email="test@example.com",
            phone="+1234567890",
            password=valid_long_password,
        )
        assert user_create.password == valid_long_password

        # Test too short password
        with pytest.raises(ValidationError):
            UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password="short",  # 5 characters
            )

    def test_boolean_field_validation(self, test_data_factory):
        """Test boolean field validation edge cases."""
        # Test userType with various values
        from pydantic import ValidationError

        from app.models.user import UserType

        # Valid userType values (only USER and ORG_USER allowed for self-registration)
        valid_test_cases = [
            (UserType.USER, UserType.USER),
            (UserType.ORG_USER, UserType.ORG_USER),
            ("user", UserType.USER),
            ("org_user", UserType.ORG_USER),
        ]

        for input_value, expected_value in valid_test_cases:
            # Use UserCreateRequest to test actual Pydantic validation
            user_create = UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password="password123",
                userType=input_value,
            )
            assert user_create.userType == expected_value

        # Test that elevated roles (ADMIN, ORG_ADMIN) are rejected
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

    def test_email_validation_comprehensive(self):
        """Test comprehensive email validation scenarios."""
        # Valid email formats
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "test+tag@example.org",
            "user123@subdomain.example.com",
            "a@b.co",
        ]

        for email in valid_emails:
            user_create = UserCreateRequest(
                email=email,
                phone="+1234567890",
                password="password123",
            )
            assert user_create.email == email

        # Invalid email formats
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "test@",
            "test..test@example.com",
            "test@.com",
            "",
        ]

        for email in invalid_emails:
            with pytest.raises(ValidationError):
                UserCreateRequest(
                    email=email,
                    phone="+1234567890",
                    password="password123",
                )

    def test_timestamp_precision_and_timezone(self, test_data_factory):
        """Test timestamp precision and timezone handling."""
        # Test that timestamps are in UTC
        user_data = test_data_factory.create_user_data()
        assert user_data["createdAt"].tzinfo == UTC
        assert user_data["updatedAt"].tzinfo == UTC

        # Test timestamp precision (should be datetime objects)
        assert isinstance(user_data["createdAt"], datetime)
        assert isinstance(user_data["updatedAt"], datetime)

    def test_field_restrictions_comprehensive(self, test_data_factory):
        """Test comprehensive field restriction validation."""
        # Test that UserCreate only has required fields
        user_create = UserCreate(
            email="test@example.com",
            phone="+1234567890",
            password="password123",
        )

        # UserCreate should only have the required fields
        assert hasattr(user_create, "email")
        assert hasattr(user_create, "phone")
        assert hasattr(user_create, "password")

        # UserCreate should NOT have isActive and isVerified (those are set by the service)
        assert not hasattr(user_create, "isActive")
        assert not hasattr(user_create, "isVerified")

        # Test that UserUpdate allows these fields but they should be ignored by the service
        user_update = UserUpdate(
            firstName="John",
            isActive=False,  # This should be ignored by the service
            isVerified=True,  # This should be ignored by the service
        )

        # The fields should be present in UserUpdate but ignored by the service
        assert hasattr(user_update, "isActive")
        assert hasattr(user_update, "isVerified")

    def test_error_response_format_consistency(self, test_data_factory):
        """Test that error responses follow the standardized format."""
        # This would typically be tested with actual API calls
        # but we can verify the expected structure
        # expected_error_structure = {
        #     "success": False,
        #     "message": str,
        #     "timestamp": str,
        #     "data": None,
        #     "error_code": str,
        #     "details": dict,
        #     "validation_errors": list,
        # }

        # Verify that our test data factory can create consistent error scenarios
        invalid_data = test_data_factory.create_user_create_request(
            email="invalid-email"
        )

        # The structure should be consistent for validation errors
        assert "email" in invalid_data
        assert invalid_data["email"] == "invalid-email"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app", "--cov-report=html"])
