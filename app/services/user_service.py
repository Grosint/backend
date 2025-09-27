from __future__ import annotations

import logging
from datetime import UTC, datetime

from bson import ObjectId

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.user import UserCreate, UserInDB, UserUpdate

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db):
        self.db = db
        self.collection = db[settings.MONGODB_COLLECTION_USERS]

    async def create_user(self, user: UserCreate) -> UserInDB:
        """Create a new user"""
        try:
            # Check if user already exists
            existing_user = await self.get_user_by_email(user.email)
            if existing_user:
                raise ValueError("User with this email already exists")

            # Hash password
            hashed_password = get_password_hash(user.password)

            # Create user document
            current_time = datetime.now(UTC)
            user_doc = {
                "email": user.email,
                "password": hashed_password,
                "phone": user.phone,
                "verifyByGovId": user.verifyByGovId,
                "firstName": None,
                "lastName": None,
                "pinCode": None,
                "state": None,
                "isActive": True,
                "isVerified": False,
                "createdAt": current_time,
                "updatedAt": current_time,
            }

            result = await self.collection.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id

            logger.info(f"User created: {user.email}")
            return UserInDB(**user_doc)

        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def get_user_by_id(self, user_id: str) -> UserInDB | None:
        """Get user by ID"""
        try:
            user_doc = await self.collection.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                return UserInDB(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            raise

    async def get_user_by_email(self, email: str) -> UserInDB | None:
        """Get user by email"""
        try:
            user_doc = await self.collection.find_one({"email": email})
            if user_doc:
                return UserInDB(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            raise

    async def get_user_by_username(self, username: str) -> UserInDB | None:
        """Get user by username"""
        try:
            user_doc = await self.collection.find_one({"username": username})
            if user_doc:
                return UserInDB(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by username: {e}")
            raise

    async def authenticate_user(self, email: str, password: str) -> UserInDB | None:
        """Authenticate user with email and password"""
        try:
            user = await self.get_user_by_email(email)
            if not user:
                return None

            if not verify_password(password, user.hashed_password):
                return None

            if not user.is_active:
                return None

            return user
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            raise

    async def update_user(
        self, user_id: str, user_update: UserUpdate
    ) -> UserInDB | None:
        """Update user"""
        try:
            update_data = user_update.dict(exclude_unset=True)
            if not update_data:
                return await self.get_user_by_id(user_id)

            update_data["updatedAt"] = datetime.now(UTC)

            result = await self.collection.update_one(
                {"_id": ObjectId(user_id)}, {"$set": update_data}
            )

            if result.modified_count:
                return await self.get_user_by_id(user_id)
            return None
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise

    async def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            raise

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[UserInDB]:
        """List users with pagination"""
        try:
            cursor = self.collection.find().skip(skip).limit(limit)
            users = []
            async for user_doc in cursor:
                users.append(UserInDB(**user_doc))
            return users
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            raise
