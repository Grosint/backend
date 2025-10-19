"""
Test to verify Docker MongoDB setup is working correctly.
"""

import pytest
from pymongo.errors import ServerSelectionTimeoutError


@pytest.mark.asyncio
async def test_mongodb_connection(test_db):
    """Test that we can connect to the MongoDB container."""
    # Test basic connection
    assert test_db is not None

    try:
        # Test that we can perform operations
        test_collection = test_db["test_connection"]

        # Insert a test document (async operation)
        result = await test_collection.insert_one({"test": "data", "value": 123})
        assert result.inserted_id is not None

        # Find the document (async operation)
        document = await test_collection.find_one({"test": "data"})
        assert document is not None
        assert document["value"] == 123

        # Clean up (async operation)
        await test_collection.drop()

    except ServerSelectionTimeoutError:
        pytest.skip(
            "MongoDB container is not running. Start with: docker-compose -f docker-compose.test.yml up -d"
        )


@pytest.mark.asyncio
async def test_database_cleanup(test_db):
    """Test that database cleanup works properly."""
    # Clean up any existing data first
    users_collection = test_db["users"]
    searches_collection = test_db["searches"]
    results_collection = test_db["results"]

    # Clear existing data
    await users_collection.drop()
    await searches_collection.drop()
    await results_collection.drop()

    # Insert test data (async operations)
    await users_collection.insert_one({"email": "test@example.com"})
    await searches_collection.insert_one({"query": "test search"})
    await results_collection.insert_one({"result": "test result"})

    # Verify data exists (async operations)
    user_count = await users_collection.count_documents({})
    search_count = await searches_collection.count_documents({})
    result_count = await results_collection.count_documents({})

    assert user_count == 1
    assert search_count == 1
    assert result_count == 1

    # Clean up after test
    await users_collection.drop()
    await searches_collection.drop()
    await results_collection.drop()
