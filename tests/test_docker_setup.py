"""
Test to verify Docker MongoDB setup is working correctly.
"""


def test_mongodb_connection(test_db):
    """Test that we can connect to the MongoDB container."""
    # Test basic connection
    assert test_db is not None

    # Test that we can perform operations
    test_collection = test_db["test_connection"]

    # Insert a test document (synchronous operation)
    result = test_collection.insert_one({"test": "data", "value": 123})
    assert result.inserted_id is not None

    # Find the document (synchronous operation)
    document = test_collection.find_one({"test": "data"})
    assert document is not None
    assert document["value"] == 123

    # Clean up (synchronous operation)
    test_collection.drop()


def test_database_cleanup(test_db):
    """Test that database cleanup works properly."""
    # Insert some test data
    users_collection = test_db["users"]
    searches_collection = test_db["searches"]
    results_collection = test_db["results"]

    # Insert test data (synchronous operations)
    users_collection.insert_one({"email": "test@example.com"})
    searches_collection.insert_one({"query": "test search"})
    results_collection.insert_one({"result": "test result"})

    # Verify data exists (synchronous operations)
    user_count = users_collection.count_documents({})
    search_count = searches_collection.count_documents({})
    result_count = results_collection.count_documents({})

    assert user_count == 1
    assert search_count == 1
    assert result_count == 1

    # The conftest.py should clean up these collections automatically
    # This test just verifies the collections exist and can be queried
