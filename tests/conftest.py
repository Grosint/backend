"""Test configuration and fixtures."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from beanie import init_beanie
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.database import get_database
from app.main import app
from app.models.user import User, UserInDB


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_database():
    """Mock database for testing."""
    db = MagicMock()
    db.users = MagicMock()
    db.users.find_one = AsyncMock()
    db.users.find = MagicMock()
    db.users.insert_one = AsyncMock()
    db.users.update_one = AsyncMock()
    db.users.delete_one = AsyncMock()
    db.users.count_documents = AsyncMock()
    return db


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": "user_id_123",
        "email": "test@example.com",
        "phone": "+1234567890",
        "password": "hashed_password",
        "userType": "user",
        "features": [],
        "firstName": "John",
        "lastName": "Doe",
        "pinCode": "12345",
        "state": "CA",
        "isActive": True,
        "isVerified": False,
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }


@pytest.fixture
def sample_user_in_db(sample_user_data):
    """Sample UserInDB object for testing."""
    return UserInDB(**sample_user_data)


@pytest.fixture
def sample_user_create_request():
    """Sample user creation request data."""
    return {
        "email": "test@example.com",
        "phone": "+1234567890",
        "password": "password123",
    }


@pytest.fixture
def sample_user_update_request():
    """Sample user update request data."""
    return {
        "firstName": "Jane",
        "lastName": "Smith",
        "phone": "+9876543210",
        "pinCode": "54321",
        "state": "NY",
    }


@pytest.fixture
def invalid_user_requests():
    """Invalid user request data for testing validation."""
    return {
        "invalid_email": {
            "email": "invalid-email",
            "phone": "+1234567890",
            "password": "password123",
        },
        "empty_phone": {
            "email": "test@example.com",
            "phone": "",
            "password": "password123",
        },
        "short_password": {
            "email": "test@example.com",
            "phone": "+1234567890",
            "password": "short",
        },
        "missing_required_fields": {
            "email": "test@example.com",
            # phone missing
            "password": "password123",
        },
    }


@pytest.fixture
def mock_user_service():
    """Mock UserService for testing."""
    service = MagicMock()
    service.create_user = AsyncMock()
    service.get_user_by_id = AsyncMock()
    service.update_user = AsyncMock()
    service.delete_user = AsyncMock()
    service.list_users = AsyncMock()
    service.count_users = AsyncMock()
    return service


@pytest.fixture
def mock_get_current_user(sample_user_in_db):
    """Mock get_current_user dependency."""
    return sample_user_in_db


@pytest.fixture(autouse=True)
def mock_database_dependency(mock_database):
    """Mock database dependency for all tests."""
    app.dependency_overrides[get_database] = lambda: mock_database
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_password_hashing():
    """Mock password hashing functions."""
    with pytest.MonkeyPatch().context() as m:
        m.setattr(
            "app.services.user_service.get_password_hash", lambda x: f"hashed_{x}"
        )
        m.setattr(
            "app.services.user_service.verify_password",
            lambda x, y: x == y.replace("hashed_", ""),
        )
        yield


@pytest.fixture
def mock_beanie_operations():
    """Mock Beanie operations."""
    with pytest.MonkeyPatch().context() as m:
        # Mock User.find_one
        m.setattr("app.models.user.User.find_one", AsyncMock())
        # Mock User.insert
        m.setattr("app.models.user.User.insert", AsyncMock())
        # Mock User.save
        m.setattr("app.models.user.User.save", AsyncMock())
        # Mock User.delete
        m.setattr("app.models.user.User.delete", AsyncMock())
        yield


class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def create_user_data(**overrides):
        """Create user data with optional overrides."""
        default_data = {
            "email": "test@example.com",
            "phone": "+1234567890",
            "password": "hashed_password",
            "userType": "user",
            "features": [],
            "firstName": "John",
            "lastName": "Doe",
            "pinCode": "12345",
            "state": "CA",
            "isActive": True,
            "isVerified": False,
            "createdAt": datetime.now(UTC),
            "updatedAt": datetime.now(UTC),
        }
        default_data.update(overrides)
        return default_data

    @staticmethod
    def create_user_create_request(**overrides):
        """Create user creation request with optional overrides."""
        default_data = {
            "email": "test@example.com",
            "phone": "+1234567890",
            "password": "password123",
        }
        default_data.update(overrides)
        return default_data

    @staticmethod
    def create_user_update_request(**overrides):
        """Create user update request with optional overrides."""
        default_data = {
            "firstName": "Jane",
            "lastName": "Smith",
            "phone": "+9876543210",
        }
        default_data.update(overrides)
        return default_data


@pytest.fixture
def test_data_factory():
    """Test data factory fixture."""
    return TestDataFactory()


@pytest.fixture
async def beanie_init():
    """Initialize Beanie for tests that need it."""
    # Create a test database connection
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    database = client.test_grosint

    # Initialize Beanie with test database
    await init_beanie(database=database, document_models=[User])

    yield database

    # Cleanup
    await client.close()


@pytest.fixture
def test_db():
    """Test database fixture for MongoDB connection tests."""
    from motor.motor_asyncio import AsyncIOMotorClient

    # Connect to test MongoDB instance without authentication first
    # The container is configured with auth but we need to connect to admin first
    client = AsyncIOMotorClient("mongodb://testuser:testpass@localhost:27018/admin")
    database = client.test_osint_backend

    return database
