from __future__ import annotations

import logging
from urllib.parse import urlparse

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

from app.core.config import settings

logger = logging.getLogger(__name__)


def extract_database_name_from_url(mongodb_url: str) -> str:
    """Extract database name from MongoDB URL"""
    try:
        parsed_url = urlparse(mongodb_url)
        # Get the path after the first slash, remove leading slash
        database_name = parsed_url.path.lstrip("/")

        # If no database specified in URL, use default
        if not database_name:
            return settings.MONGODB_DATABASE

        return database_name
    except Exception as e:
        logger.warning(f"Could not extract database name from URL: {e}. Using default.")
        return settings.MONGODB_DATABASE


class Database:
    client: AsyncIOMotorClient | None = None
    database = None


db = Database()


async def get_database():
    """Get database instance"""
    return db.database


async def connect_to_mongo():
    """Create database connection"""
    # MONGODB_URL is validated at startup, but type checker needs assurance
    if not settings.MONGODB_URL:
        raise ValueError(
            "MONGODB_URL is required but was not set. "
            "This should have been caught at startup."
        )

    # Type narrowing: after the check above, MONGODB_URL is guaranteed to be str
    mongodb_url: str = settings.MONGODB_URL

    try:
        db.client = AsyncIOMotorClient(mongodb_url)

        # Extract database name from URL or use default
        database_name = extract_database_name_from_url(mongodb_url)
        db.database = db.client[database_name]

        # Test the connection
        await db.client.admin.command("ping")

        # Log connection with masked credentials
        masked_url = mongodb_url
        if "@" in masked_url:
            # Mask the password in the URL
            parts = masked_url.split("@")
            if len(parts) == 2:
                user_pass = parts[0].split("://")[-1]
                if ":" in user_pass:
                    user, _ = user_pass.split(":", 1)
                    masked_url = masked_url.replace(user_pass, f"{user}:***")

        logger.info(f"Connected to MongoDB at {masked_url}")

        # Migrate indexes: Drop old unique email index if it exists
        await migrate_user_indexes(db.database)

        # Initialize Beanie with document models
        from app.models.credit import Credit
        from app.models.credit_txn import CreditTxn
        from app.models.history import History
        from app.models.organization import Organization
        from app.models.payment import Payment
        from app.models.plan import Plan
        from app.models.result import Result
        from app.models.search import Search
        from app.models.subscription import Subscription
        from app.models.user import User  # local import to avoid circulars

        await init_beanie(
            database=db.database,
            document_models=[
                User,
                Organization,
                History,
                Search,
                Result,
                Plan,
                Payment,
                Subscription,
                Credit,
                CreditTxn,
            ],
        )
        logger.info("Initialized Beanie")

        # Initialize non-Beanie collection indexes (e.g., email_otps)
        await initialize_collection_indexes(db.database)

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


async def migrate_user_indexes(database):
    """
    Migrate user collection indexes.

    Drops the old unique email index if it exists to allow non-unique email index.
    This is needed when migrating from email-unique to phone-unique schema.

    Args:
        database: MongoDB database instance
    """
    try:
        users_collection = database.users
        indexes = await users_collection.list_indexes().to_list(length=100)

        # Find and drop the old unique email index if it exists
        for index in indexes:
            index_name = index.get("name", "")
            index_key = index.get("key", {})
            is_unique = index.get("unique", False)

            # Check if this is the old unique email index
            if index_name == "email_1" and is_unique and "email" in index_key:
                try:
                    await users_collection.drop_index(index_name)
                    logger.info(f"Dropped old unique email index: {index_name}")
                except Exception as e:
                    logger.warning(f"Could not drop index {index_name}: {e}")
                    # Continue - Beanie will handle the conflict or we can manually fix it

    except Exception as e:
        logger.warning(f"Error migrating user indexes: {e}")
        # Don't raise - allow application to start even if migration fails
        # The index conflict will be handled by Beanie or can be fixed manually


async def initialize_collection_indexes(database):
    """
    Initialize indexes for non-Beanie collections.

    This function creates indexes for collections that are not managed by Beanie,
    such as email_otps, blocked_tokens, etc.

    Args:
        database: MongoDB database instance
    """
    try:
        from pymongo import ASCENDING

        # Create TTL index for email_otps collection
        email_otps_collection = database.email_otps
        indexes = await email_otps_collection.list_indexes().to_list(length=100)
        index_names = [idx["name"] for idx in indexes]

        if "expires_at_1" not in index_names:
            await email_otps_collection.create_index(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,  # Documents expire when expires_at is reached
                background=True,
            )
            logger.info("Created TTL index for email_otps collection")
        else:
            logger.debug("TTL index for email_otps collection already exists")

    except Exception as e:
        logger.error(f"Error initializing collection indexes: {e}", exc_info=True)
        # Don't raise - allow application to start even if index creation fails
        # Indexes might already exist or be created manually


async def create_indexes():
    """Deprecated: Indexes are now defined on Beanie models."""
    logger.info(
        "create_indexes is deprecated; Beanie manages indexes from model definitions"
    )
