"""Email OTP utilities for user verification."""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from pymongo import ASCENDING

logger = logging.getLogger(__name__)

# OTP configuration
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10


def generate_otp(length: int = OTP_LENGTH) -> str:
    """
    Generate a random OTP (One-Time Password).

    Args:
        length: Length of OTP (default: 6)

    Returns:
        Random OTP string
    """
    return "".join(secrets.choice("0123456789") for _ in range(length))


async def store_otp(
    database, email: str, otp: str, expires_in_minutes: int = OTP_EXPIRY_MINUTES
) -> bool:
    """
    Store OTP in database with expiration.

    Args:
        database: Database instance
        email: User email
        otp: Generated OTP
        expires_in_minutes: OTP expiration time in minutes

    Returns:
        True if OTP stored successfully
    """
    try:
        collection = database.email_otps

        # Normalize email to lowercase for consistent comparison
        email = email.lower().strip()

        # Create TTL index if it doesn't exist
        indexes = await collection.list_indexes().to_list(length=100)
        index_names = [idx["name"] for idx in indexes]
        if "expires_at_1" not in index_names:
            collection.create_index(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                background=True,
            )

        # Calculate expiration time
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)

        # Store OTP (normalize OTP by stripping whitespace)
        otp_doc = {
            "email": email,
            "otp": otp.strip(),
            "expires_at": expires_at,
            "created_at": datetime.now(UTC),
            "verified": False,
        }

        # Remove any existing OTPs for this email (normalized to lowercase)
        await collection.delete_many({"email": email})

        # Insert new OTP
        await collection.insert_one(otp_doc)

        logger.info(f"OTP stored for email: {email[:5]}***")
        return True

    except Exception as e:
        logger.error(f"Error storing OTP: {e}")
        return False


async def verify_otp(database, email: str, otp: str) -> bool:
    """
    Verify OTP for email.

    Args:
        database: Database instance
        email: User email
        otp: OTP to verify

    Returns:
        True if OTP is valid and not expired
    """
    try:
        collection = database.email_otps

        # Normalize email and OTP for comparison
        email = email.lower().strip()
        otp = otp.strip()

        # Find OTP document (email is normalized to lowercase)
        otp_doc = await collection.find_one(
            {
                "email": email,
                "otp": otp,
                "verified": False,
            }
        )

        if not otp_doc:
            # Check if OTP exists but OTP doesn't match
            existing_otp = await collection.find_one(
                {"email": email, "verified": False}
            )
            if existing_otp:
                logger.warning(
                    f"Invalid OTP attempt for email: {email[:5]}***. "
                    "Stored OTP does not match provided value."
                )
            else:
                logger.warning(f"No OTP found for email: {email[:5]}***")
            return False

        # Check if OTP is expired
        expires_at = otp_doc.get("expires_at")
        if expires_at:
            # Handle both timezone-aware and timezone-naive datetimes
            current_time = datetime.now(UTC)

            # If expires_at is timezone-naive, assume it's UTC
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            if current_time > expires_at:
                logger.warning(
                    f"Expired OTP attempt for email: {email[:5]}***. "
                    f"Expired at: {expires_at}, Current time: {current_time}"
                )
                await collection.delete_one({"_id": otp_doc["_id"]})
                return False

        # Mark OTP as verified
        await collection.update_one(
            {"_id": otp_doc["_id"]}, {"$set": {"verified": True}}
        )

        logger.info(f"OTP verified successfully for email: {email[:5]}***")
        return True

    except Exception as e:
        logger.error(f"Error verifying OTP: {e}", exc_info=True)
        return False


async def send_otp_email(
    email: str, otp: str, expires_in_minutes: int = OTP_EXPIRY_MINUTES
) -> bool:
    """
    Send OTP email to user using Azure Communication Services.

    Args:
        email: User email address
        otp: Generated OTP
        expires_in_minutes: OTP expiration time in minutes (default: 10)

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        from app.services.email_service import email_service

        logger.info(f"Sending OTP email to {email[:5]}***")
        result = await email_service.send_otp_email(
            email=email,
            otp=otp,
            expires_in_minutes=expires_in_minutes,
        )

        if result:
            logger.info(f"OTP email sent successfully to {email[:5]}***")
        else:
            logger.warning(f"Failed to send OTP email to {email[:5]}***")

        return result

    except Exception as e:
        logger.error(f"Error sending OTP email: {e}")
        return False


async def get_otp_for_email(database, email: str) -> dict | None:
    """
    Get current OTP for email (for testing/debugging purposes).

    Args:
        database: Database instance
        email: User email

    Returns:
        OTP document or None if not found
    """
    try:
        collection = database.email_otps
        # Normalize email to lowercase
        email = email.lower().strip()
        otp_doc = await collection.find_one(
            {"email": email, "verified": False}, sort=[("created_at", -1)]
        )
        return otp_doc

    except Exception as e:
        logger.error(f"Error getting OTP for email: {e}")
        return None


async def delete_otp(database, email: str) -> bool:
    """
    Delete OTP for email.

    Args:
        database: Database instance
        email: User email

    Returns:
        True if OTP deleted successfully
    """
    try:
        collection = database.email_otps
        # Normalize email to lowercase
        email = email.lower().strip()
        result = await collection.delete_many({"email": email})
        logger.info(f"Deleted {result.deleted_count} OTP(s) for email: {email[:5]}***")
        return result.deleted_count > 0

    except Exception as e:
        logger.error(f"Error deleting OTP: {e}")
        return False
