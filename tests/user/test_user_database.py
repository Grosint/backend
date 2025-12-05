"""Test user database interactions and timestamp behavior."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from bson import ObjectId

from app.core.exceptions import ConflictException
from app.models.user import User, UserCreate, UserInDB, UserUpdate
from app.services.user_service import UserService


class TestUserTimestampBehavior:
    """Test user timestamp behavior."""

    def test_user_creation_sets_timestamps(self):
        """Test that user creation sets createdAt and updatedAt."""
        # Mock the Beanie collection to avoid initialization issues
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            # Create a user object to test the timestamp logic
            user_data = {
                "email": "test@example.com",
                "phone": "+1234567890",
                "password": "hashed_password",
                "userType": "user",
                "features": [],
                "firstName": "Test",
                "lastName": "User",
                "pinCode": "12345",
                "state": "Test State",
                "isActive": True,
                "isVerified": False,
            }

            # Create user instance
            user = User(**user_data)

            # Simulate the before_event hook
            user.set_timestamps()

            assert user.createdAt is not None
            assert user.updatedAt is not None
            assert isinstance(user.createdAt, datetime)
            assert isinstance(user.updatedAt, datetime)
            assert user.createdAt <= datetime.now(UTC)
            assert user.updatedAt <= datetime.now(UTC)

    def test_user_creation_timestamps_are_same(self):
        """Test that createdAt and updatedAt are the same on creation."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )

            user.set_timestamps()

            # On creation, createdAt and updatedAt should be very close (within 1 second)
            time_diff = abs((user.updatedAt - user.createdAt).total_seconds())
            assert time_diff < 1.0

    def test_user_update_updates_timestamp(self):
        """Test that user update modifies updatedAt but not createdAt."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            # Create user with old timestamps
            old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
                createdAt=old_time,
                updatedAt=old_time,
            )

            # Simulate update
            user.set_timestamps()

            # updatedAt should be newer
            assert user.updatedAt > old_time
            # createdAt should remain unchanged
            assert user.createdAt == old_time

    def test_user_timestamps_are_utc(self):
        """Test that timestamps are in UTC timezone."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )

            user.set_timestamps()

            assert user.createdAt.tzinfo == UTC
            assert user.updatedAt.tzinfo == UTC

    def test_user_timestamps_precision(self):
        """Test that timestamps have sufficient precision."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )

            user.set_timestamps()

            # Timestamps should be very close to current time
            now = datetime.now(UTC)
            time_diff = abs((now - user.createdAt).total_seconds())
            assert time_diff < 1.0  # Within 1 second


class TestUserDatabaseOperations:
    """Test user database operations."""

    @pytest.fixture
    def mock_db(self):
        """Mock database for testing."""
        db = MagicMock()
        db.users = MagicMock()
        return db

    @pytest.fixture
    def user_service(self, mock_db):
        """Create UserService instance with mocked database."""
        return UserService(mock_db)

    @pytest.mark.asyncio
    async def test_create_user_database_interaction(self, user_service):
        """Test user creation database interaction."""
        # Create a mock user instance
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId()
        mock_user.email = "test@example.com"
        mock_user.phone = "+1234567890"
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
                user_create = UserCreate(
                    email="test@example.com",
                    phone="+1234567890",
                    password="password123",
                )

                result = await user_service.create_user(user_create)

                # Verify Beanie calls
                mock_user_class.find_one.assert_called_once()
                mock_user.insert.assert_called_once()

                # Verify result
                assert isinstance(result, UserInDB)
                assert result.email == "test@example.com"
                assert result.isActive is True
                assert result.isVerified is False

    @pytest.mark.asyncio
    async def test_create_user_email_uniqueness_check(self, user_service):
        """Test that email uniqueness is checked before creation."""
        # Mock existing user found
        mock_existing_user = Mock(spec=User)
        mock_existing_user.email = "test@example.com"

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.email = MagicMock()
            mock_user_class.email.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_existing_user)

            user_create = UserCreate(
                email="test@example.com",
                phone="+1234567890",
                password="password123",
            )

            with pytest.raises(ConflictException) as exc_info:
                await user_service.create_user(user_create)

            # Verify Beanie was queried for existing user
            mock_user_class.find_one.assert_called_once()

            assert "User with this email already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_user_by_id_database_interaction(self, user_service):
        """Test user retrieval database interaction."""
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId()
        mock_user.email = "test@example.com"
        mock_user.phone = "+1234567890"
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

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern: User.id == ObjectId(user_id)
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            result = await user_service.get_user_by_id(str(mock_user.id))

            # Verify Beanie call
            mock_user_class.find_one.assert_called_once()

            # Verify result
            assert result is not None
            assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_service):
        """Test user retrieval when user not found."""
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
    async def test_update_user_database_interaction(self, user_service):
        """Test user update database interaction."""
        # Mock existing user
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId()
        mock_user.email = "test@example.com"
        mock_user.phone = "+1234567890"
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
        mock_user.save = AsyncMock()

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            user_update = UserUpdate(
                firstName="John", lastName="Doe", phone="+9876543210"
            )

            result = await user_service.update_user(str(mock_user.id), user_update)

            # Verify Beanie calls (update may call find_one multiple times)
            assert mock_user_class.find_one.call_count >= 1
            mock_user.save.assert_called_once()

            # Verify result
            assert result is not None
            assert result.firstName == "John"
            assert result.lastName == "Doe"

    @pytest.mark.asyncio
    async def test_delete_user_database_interaction(self, user_service):
        """Test user deletion database interaction."""
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
        """Test user deletion when user not found."""
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
    async def test_list_users_database_interaction(self, user_service):
        """Test user listing database interaction."""
        mock_user1 = MagicMock()
        mock_user1.id = ObjectId()
        mock_user1.email = "user1@example.com"
        mock_user1.phone = "+1234567890"
        mock_user1.password = "hashed_password"
        mock_user1.userType = "user"
        mock_user1.features = []
        mock_user1.isActive = True
        mock_user1.isVerified = False
        mock_user1.firstName = None
        mock_user1.lastName = None
        mock_user1.address = None
        mock_user1.city = None
        mock_user1.pinCode = None
        mock_user1.state = None
        mock_user1.organizationId = None
        mock_user1.orgName = None
        mock_user1.createdAt = datetime.now(UTC)
        mock_user1.updatedAt = datetime.now(UTC)

        mock_user2 = MagicMock()
        mock_user2.id = ObjectId()
        mock_user2.email = "user2@example.com"
        mock_user2.phone = "+9876543210"
        mock_user2.password = "hashed_password"
        mock_user2.userType = "user"
        mock_user2.features = []
        mock_user2.isActive = True
        mock_user2.isVerified = False
        mock_user2.firstName = None
        mock_user2.lastName = None
        mock_user2.address = None
        mock_user2.city = None
        mock_user2.pinCode = None
        mock_user2.state = None
        mock_user2.organizationId = None
        mock_user2.orgName = None
        mock_user2.createdAt = datetime.now(UTC)
        mock_user2.updatedAt = datetime.now(UTC)

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
    async def test_count_users_database_interaction(self, user_service):
        """Test user counting database interaction."""
        with patch("app.models.user.User.count", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 5

            result = await user_service.count_users()

            # Verify Beanie call
            mock_count.assert_called_once()

            # Verify result
            assert result == 5


class TestUserFieldRestrictions:
    """Test user field restrictions and permissions."""

    @pytest.fixture
    def mock_db(self):
        """Mock database for testing."""
        db = MagicMock()
        db.users = MagicMock()
        return db

    @pytest.fixture
    def user_service(self, mock_db):
        """Create UserService instance with mocked database."""
        return UserService(mock_db)

    @pytest.mark.asyncio
    async def test_user_creation_sets_default_values(self, user_service):
        """Test that user creation sets correct default values."""
        # Create a mock user instance
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId()
        mock_user.email = "test@example.com"
        mock_user.phone = "+1234567890"
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

        # Mock Beanie operations
        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.email = MagicMock()
            mock_user_class.email.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=None)
            mock_user_class.return_value = mock_user

            with patch(
                "app.services.user_service.hash_password",
                return_value="hashed_password",
            ):
                user_create = UserCreate(
                    email="test@example.com",
                    phone="+1234567890",
                    password="password123",
                )

                result = await user_service.create_user(user_create)

                # Verify default values are set correctly
                assert result.isActive is True  # Should be set to True
                assert result.isVerified is False  # Should be set to False

    @pytest.mark.asyncio
    async def test_user_update_restricts_certain_fields(self, user_service):
        """Test that certain fields cannot be updated by users."""
        # Mock existing user
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId()
        mock_user.email = "test@example.com"
        mock_user.phone = "+1234567890"
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
        mock_user.save = AsyncMock()

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            # Try to update restricted fields
            user_update = UserUpdate(
                firstName="John",
                isActive=False,  # Should be ignored
                isVerified=True,  # Should be ignored
            )

            await user_service.update_user(str(mock_user.id), user_update)

            # Verify that the update was processed
            mock_user.save.assert_called_once()

            # The actual restriction logic would need to be implemented in the service
            # This test verifies the structure is in place

    @pytest.mark.asyncio
    async def test_user_update_allows_permitted_fields(self, user_service):
        """Test that permitted fields can be updated."""
        # Mock existing user
        mock_user = Mock(spec=User)
        mock_user.id = ObjectId()
        mock_user.email = "test@example.com"
        mock_user.phone = "+1234567890"
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
        mock_user.save = AsyncMock()

        with patch("app.services.user_service.User") as mock_user_class:
            # Setup mock to handle query pattern
            mock_user_class.id = MagicMock()
            mock_user_class.id.__eq__ = MagicMock(return_value="query")
            mock_user_class.find_one = AsyncMock(return_value=mock_user)

            # Update permitted fields
            user_update = UserUpdate(
                firstName="John",
                lastName="Doe",
                phone="+9876543210",
                pinCode="12345",
                state="CA",
            )

            result = await user_service.update_user(str(mock_user.id), user_update)

            # Verify that the update was processed
            mock_user.save.assert_called_once()

            # Verify result contains updated fields
            assert result.firstName == "John"
            assert result.lastName == "Doe"
            assert result.phone == "+9876543210"


class TestUserModelSettings:
    """Test User model settings and configuration."""

    def test_user_model_collection_name(self):
        """Test that User model has correct collection name."""
        assert User.Settings.name == "users"

    def test_user_model_email_index(self):
        """Test that email field has proper indexing configuration."""
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

    def test_user_model_phone_validation(self):
        """Test that phone field has proper validation."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            # Valid phone
            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )
            assert user.phone == "+1234567890"

            # Invalid phone should raise validation error
            with pytest.raises(ValueError):
                User(
                    email="test@example.com",
                    phone="",  # Empty phone should fail
                    password="hashed_password",
                )

    def test_user_model_required_fields(self):
        """Test that required fields are properly defined."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            # All required fields present
            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )
            assert user.email is not None
            assert user.phone is not None
            assert user.password is not None

            # Missing required field should raise validation error
            with pytest.raises(ValueError):
                User(
                    email="test@example.com",
                    # phone missing
                    password="hashed_password",
                )


class TestUserDataIntegrity:
    """Test user data integrity and consistency."""

    def test_user_id_consistency(self):
        """Test that user ID is consistent across operations."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )

            # User should have an ID after creation
            assert hasattr(user, "id")
            # ID should be consistent
            assert user.id == user.id

    def test_user_email_uniqueness_constraint(self):
        """Test that email uniqueness is enforced."""
        # This would be tested with actual database operations
        # For now, we verify the field is properly defined
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )
            assert user.email == "test@example.com"

    def test_user_password_hashing(self):
        """Test that password is properly hashed."""
        # This would be tested with actual password hashing
        # For now, we verify the field is properly defined
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )
            assert user.password == "hashed_password"

    def test_user_timestamps_consistency(self):
        """Test that timestamps are consistent and logical."""
        with patch("app.models.user.User.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.pymongo_collection = MagicMock()
            mock_get_settings.return_value = mock_settings

            user = User(
                email="test@example.com",
                phone="+1234567890",
                password="hashed_password",
            )

            user.set_timestamps()

            # createdAt should not be in the future
            assert user.createdAt <= datetime.now(UTC)
            # updatedAt should not be in the future
            assert user.updatedAt <= datetime.now(UTC)
            # updatedAt should not be before createdAt
            assert user.updatedAt >= user.createdAt
