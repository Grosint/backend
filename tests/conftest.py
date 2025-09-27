import asyncio
import os
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_database
from app.main import app


# Load test environment variables
def load_test_env():
    """Load test environment variables from .env.test file"""
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env.test")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Set environment variable with high priority
                    os.environ[key] = value
        print(f"Loaded test environment from {env_file}")
        print(f"MONGODB_URL: {os.environ.get('MONGODB_URL', 'NOT SET')}")
        print(f"MONGODB_DATABASE: {os.environ.get('MONGODB_DATABASE', 'NOT SET')}")


# Load test environment before importing other modules
load_test_env()

# Test database configuration
# Using Docker MongoDB for tests
TEST_DATABASE_URL = os.getenv(
    "MONGODB_URL", "mongodb://testuser:testpass@localhost:27018"
)
TEST_DATABASE_NAME = os.getenv("MONGODB_DATABASE", "test_osint_backend")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def docker_compose_file():
    """Return the path to the docker-compose file for testing."""
    return os.path.join(os.path.dirname(__file__), "..", "docker-compose.test.yml")


@pytest.fixture(scope="session")
def docker_services(docker_compose_file):
    """Start Docker services for testing."""
    # Temporarily rename .env file to prevent production config loading
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_backup = env_file + ".backup"

    if os.path.exists(env_file):
        os.rename(env_file, env_backup)

    try:
        # Start the services
        subprocess.run(
            ["docker", "compose", "-f", docker_compose_file, "up", "-d", "--build"],
            check=True,
        )

        # Wait for MongoDB to be ready
        max_retries = 30
        for _ in range(max_retries):
            try:
                # Try to connect to MongoDB
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "osint-backend-test-mongodb",
                        "mongosh",
                        "--eval",
                        "db.adminCommand('ping')",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if "ok" in result.stdout.lower():
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(1)
        else:
            raise Exception("MongoDB container failed to start or become ready")

        yield

    finally:
        # Clean up: stop and remove containers
        subprocess.run(
            ["docker", "compose", "-f", docker_compose_file, "down", "-v"], check=False
        )

        # Restore .env file
        if os.path.exists(env_backup):
            os.rename(env_backup, env_file)


@pytest.fixture(scope="session")
def test_db_session(docker_services):
    """Create a session-scoped test database connection"""
    from pymongo import MongoClient  # Use sync client for session scope

    try:
        # Use synchronous client for session scope to avoid event loop issues
        client = MongoClient(TEST_DATABASE_URL)
        db = client[TEST_DATABASE_NAME]

        # Test the connection
        client.admin.command("ping")

        yield db

        # Clean up
        client.close()
    except Exception as e:
        print(f"MongoDB connection error: {e}")
        pytest.skip(f"MongoDB not available: {e}")


@pytest.fixture
def test_db(test_db_session):
    """Create a test database connection with cleanup"""

    # Use sync client for cleanup to avoid event loop issues
    def cleanup_before():
        test_db_session.drop_collection("users")
        test_db_session.drop_collection("searches")
        test_db_session.drop_collection("results")

    def cleanup_after():
        test_db_session.drop_collection("users")
        test_db_session.drop_collection("searches")
        test_db_session.drop_collection("results")

    # Clean up before test
    cleanup_before()

    yield test_db_session

    # Clean up after test
    cleanup_after()


@pytest.fixture
def client(test_db):
    """Create a test client with database override"""

    # Create an async wrapper for the sync database
    class AsyncDatabaseWrapper:
        def __init__(self, sync_db):
            self.sync_db = sync_db

        def __getattr__(self, name):
            return getattr(self.sync_db, name)

        def __getitem__(self, key):
            # Return a collection wrapper that handles async operations
            collection = self.sync_db[key]
            return AsyncCollectionWrapper(collection)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Create an async wrapper for collections
    class AsyncCollectionWrapper:
        def __init__(self, sync_collection):
            self.sync_collection = sync_collection

        def __getattr__(self, name):
            return getattr(self.sync_collection, name)

        async def insert_one(self, document):
            # Convert async call to sync
            import asyncio

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.sync_collection.insert_one, document
            )

        async def find_one(self, filter):
            # Convert async call to sync
            import asyncio

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.sync_collection.find_one, filter
            )

        async def find(self, filter):
            # Convert async call to sync
            import asyncio

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.sync_collection.find, filter)

        async def update_one(self, filter, update):
            # Convert async call to sync
            import asyncio

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.sync_collection.update_one, filter, update
            )

        async def delete_one(self, filter):
            # Convert async call to sync
            import asyncio

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.sync_collection.delete_one, filter
            )

    def override_get_database():
        return AsyncDatabaseWrapper(test_db)

    app.dependency_overrides[get_database] = override_get_database

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_db):
    """Create a test user"""
    import asyncio

    from app.models.user import UserCreate
    from app.services.user_service import UserService

    async def create_user():
        user_service = UserService(test_db)
        user_create = UserCreate(
            email="test@example.com",
            phone="+1234567890",
            password="testpassword",
            verifyByGovId=True,
        )

        user = await user_service.create_user(user_create)
        return user

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(create_user())


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers for test user"""
    response = client.post(
        "/api/v1/auth/token",
        data={"username": test_user.email, "password": "testpassword"},
    )

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
