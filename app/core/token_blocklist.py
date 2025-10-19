"""Token blocklist management for secure logout using MongoDB."""

from datetime import UTC, datetime, timedelta

from pymongo import ASCENDING


class TokenBlocklist:
    """Token blocklist manager using MongoDB."""

    def __init__(self, database):
        """Initialize blocklist with MongoDB connection."""
        self.database = database
        self.collection = database.blocked_tokens

        # Create TTL index for automatic cleanup
        self.collection.create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0,  # Documents expire when expires_at is reached
            background=True,
        )

        # Create index on jti for fast lookups
        self.collection.create_index([("jti", ASCENDING)], unique=True, background=True)

    async def add_token_to_blocklist(
        self,
        jti: str,
        user_id: str,
        token_type: str,
        expires_at: datetime | None = None,
        reason: str = "logout",
    ) -> bool:
        """
        Add token to blocklist.

        Args:
            jti: JWT ID of the token
            user_id: User ID who owns the token
            token_type: Type of token (access/refresh)
            expires_at: When the token naturally expires
            reason: Reason for blocking (logout, security, etc.)

        Returns:
            True if successfully added to blocklist
        """
        try:
            # Use token expiry or default to 30 days
            if not expires_at:
                expires_at = datetime.now(UTC) + timedelta(days=30)

            # Create blocklist entry
            blocklist_entry = {
                "jti": jti,
                "user_id": user_id,
                "token_type": token_type,
                "blocked_at": datetime.now(UTC),
                "reason": reason,
                "expires_at": expires_at,
            }

            # Store in MongoDB (will auto-expire due to TTL index)
            await self.collection.insert_one(blocklist_entry)
            return True

        except Exception as e:
            print(f"Error adding token to blocklist: {e}")
            return False

    async def is_token_blocked(self, jti: str) -> bool:
        """
        Check if token is in blocklist.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is blocked
        """
        try:
            result = await self.collection.find_one({"jti": jti})
            return result is not None
        except Exception:
            # If MongoDB is down, assume token is not blocked
            # This prevents false positives during database outages
            return False

    async def get_blocklist_entry(self, jti: str) -> dict | None:
        """
        Get blocklist entry details.

        Args:
            jti: JWT ID to look up

        Returns:
            Blocklist entry dict or None if not found
        """
        try:
            entry = await self.collection.find_one({"jti": jti})
            if entry:
                # Convert ObjectId to string for JSON serialization
                entry["_id"] = str(entry["_id"])
            return entry
        except Exception:
            return None

    async def remove_token_from_blocklist(self, jti: str) -> bool:
        """
        Remove token from blocklist (for unblocking if needed).

        Args:
            jti: JWT ID to remove

        Returns:
            True if successfully removed
        """
        try:
            result = await self.collection.delete_one({"jti": jti})
            return result.deleted_count > 0
        except Exception:
            return False

    def block_all_user_tokens(self, user_id: str, reason: str = "security") -> int:
        """
        Block all tokens for a specific user (for security incidents).

        Args:
            user_id: User ID whose tokens to block
            reason: Reason for blocking

        Returns:
            Number of tokens blocked
        """
        try:
            # This would require tracking active tokens per user
            # For now, return 0 as we don't have that tracking
            return 0
        except Exception:
            return 0

    def cleanup_expired_entries(self) -> int:
        """
        Clean up expired blocklist entries.

        Returns:
            Number of entries cleaned up
        """
        try:
            # MongoDB TTL index handles this automatically
            return 0
        except Exception:
            return 0

    def get_blocklist_stats(self) -> dict:
        """
        Get blocklist statistics.

        Returns:
            Dictionary with blocklist statistics
        """
        try:
            total_blocked = self.collection.count_documents({})
            return {
                "total_blocked_tokens": total_blocked,
                "mongodb_connected": True,
                "last_updated": datetime.now(UTC).isoformat(),
            }
        except Exception:
            return {
                "total_blocked_tokens": 0,
                "mongodb_connected": False,
                "last_updated": datetime.now(UTC).isoformat(),
            }


# Global blocklist instance (will be initialized with database)
token_blocklist = None


def get_token_blocklist(database):
    """Get or create token blocklist instance."""
    global token_blocklist
    if token_blocklist is None:
        token_blocklist = TokenBlocklist(database)
    return token_blocklist


# Convenience functions
async def add_token_to_blocklist(
    jti: str,
    user_id: str,
    token_type: str,
    expires_at: datetime | None = None,
    reason: str = "logout",
    database=None,
) -> bool:
    """Add token to blocklist."""
    if database is None:
        raise ValueError("Database instance required for token blocklist")
    blocklist = get_token_blocklist(database)
    return await blocklist.add_token_to_blocklist(
        jti, user_id, token_type, expires_at, reason
    )


async def is_token_blocked(jti: str, database=None) -> bool:
    """Check if token is blocked."""
    if database is None:
        raise ValueError("Database instance required for token blocklist")
    blocklist = get_token_blocklist(database)
    return await blocklist.is_token_blocked(jti)


async def get_blocklist_entry(jti: str, database=None) -> dict | None:
    """Get blocklist entry."""
    if database is None:
        raise ValueError("Database instance required for token blocklist")
    blocklist = get_token_blocklist(database)
    return await blocklist.get_blocklist_entry(jti)
