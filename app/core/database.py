from __future__ import annotations

import logging

from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure

from app.core.config import settings

logger = logging.getLogger(__name__)


class Database:
    client: AsyncMongoClient | None = None
    database: AsyncMongoClient | None = None


db = Database()


async def get_database():
    """Get database instance"""
    return db.database


async def connect_to_mongo():
    """Create database connection"""
    try:
        db.client = AsyncMongoClient(settings.MONGODB_URL)
        db.database = db.client[settings.MONGODB_DATABASE]

        # Test the connection
        await db.client.admin.command("ping")

        # Log connection with masked credentials
        masked_url = settings.MONGODB_URL
        if "@" in masked_url:
            # Mask the password in the URL
            parts = masked_url.split("@")
            if len(parts) == 2:
                user_pass = parts[0].split("://")[-1]
                if ":" in user_pass:
                    user, _ = user_pass.split(":", 1)
                    masked_url = masked_url.replace(user_pass, f"{user}:***")

        logger.info(f"Connected to MongoDB at {masked_url}")

        # Create indexes
        await create_indexes()

    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close database connection"""
    if db.client:
        db.client.close()
        logger.info("Disconnected from MongoDB")


async def create_indexes():
    """Create database indexes for better performance"""
    try:
        # Users collection indexes
        users_collection = db.database[settings.MONGODB_COLLECTION_USERS]
        await users_collection.create_index("email", unique=True)

        # Searches collection indexes
        searches_collection = db.database[settings.MONGODB_COLLECTION_SEARCHES]
        await searches_collection.create_index("user_id")
        await searches_collection.create_index("search_type")
        await searches_collection.create_index("created_at")

        # Results collection indexes
        results_collection = db.database[settings.MONGODB_COLLECTION_RESULTS]
        await results_collection.create_index("search_id")
        await results_collection.create_index("source")
        await results_collection.create_index("created_at")

        logger.info("Database indexes created successfully")

    except Exception as e:
        logger.error(f"Error creating database indexes: {e}")
        raise
