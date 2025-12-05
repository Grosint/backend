from __future__ import annotations

import logging
from datetime import UTC, datetime

from bson import ObjectId

from app.core.config import settings
from app.core.exceptions import ConflictException
from app.models.user import User, UserCreate, UserInDB, UserUpdate
from app.utils.password import hash_password, verify_password

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db):
        self.db = db
        self.collection = db[settings.MONGODB_COLLECTION_USERS]

    async def create_user(self, user: UserCreate) -> UserInDB:
        """Create a new user"""
        try:
            # Check if user already exists
            existing_user = await User.find_one(User.email == user.email)
            if existing_user:
                raise ConflictException(
                    message="User with this email already exists",
                    details={"email": user.email},
                )

            # Create new user document
            new_user = User(
                email=user.email,
                phone=user.phone,
                password=hash_password(user.password),
                userType=user.userType,
                features=[],
                firstName=user.firstName,
                lastName=user.lastName,
                address=user.address,
                city=user.city,
                pinCode=user.pinCode,
                state=user.state,
                organizationId=(
                    ObjectId(user.organizationId)
                    if user.organizationId
                    and not isinstance(user.organizationId, ObjectId)
                    else user.organizationId
                ),
                orgName=user.orgName,
                isActive=True,
                isVerified=False,  # Will be set to True after OTP verification
            )
            await new_user.insert()

            logger.info(f"User created: {user.email}, type: {user.userType.value}")
            return UserInDB(
                id=new_user.id,
                email=new_user.email,
                phone=new_user.phone,
                password=new_user.password,
                userType=new_user.userType,
                features=new_user.features,
                firstName=new_user.firstName,
                lastName=new_user.lastName,
                address=new_user.address,
                city=new_user.city,
                pinCode=new_user.pinCode,
                state=new_user.state,
                organizationId=new_user.organizationId,
                orgName=new_user.orgName,
                isActive=new_user.isActive,
                isVerified=new_user.isVerified,
                createdAt=new_user.createdAt,
                updatedAt=new_user.updatedAt,
            )

        except ConflictException:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    async def get_user_by_id(self, user_id: str) -> UserInDB | None:
        """Get user by ID"""
        try:
            user = await User.find_one(User.id == ObjectId(user_id))
            if user:
                return UserInDB(
                    id=user.id,
                    email=user.email,
                    phone=user.phone,
                    password=user.password,
                    userType=user.userType,
                    features=user.features,
                    firstName=user.firstName,
                    lastName=user.lastName,
                    address=user.address,
                    city=user.city,
                    pinCode=user.pinCode,
                    state=user.state,
                    organizationId=user.organizationId,
                    orgName=user.orgName,
                    isActive=user.isActive,
                    isVerified=user.isVerified,
                    createdAt=user.createdAt,
                    updatedAt=user.updatedAt,
                )
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            raise

    async def get_user_by_email(self, email: str) -> UserInDB | None:
        """Get user by email"""
        try:
            user = await User.find_one(User.email == email)
            if user:
                return UserInDB(
                    id=user.id,
                    email=user.email,
                    phone=user.phone,
                    password=user.password,
                    userType=user.userType,
                    features=user.features,
                    firstName=user.firstName,
                    lastName=user.lastName,
                    address=user.address,
                    city=user.city,
                    pinCode=user.pinCode,
                    state=user.state,
                    organizationId=user.organizationId,
                    orgName=user.orgName,
                    isActive=user.isActive,
                    isVerified=user.isVerified,
                    createdAt=user.createdAt,
                    updatedAt=user.updatedAt,
                )
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            raise

    async def get_user_by_username(self, username: str) -> UserInDB | None:
        """Get user by username (alias for email)"""
        try:
            # For now, treat username as email since we don't have a separate username field
            return await self.get_user_by_email(username)
        except Exception as e:
            logger.error(f"Error getting user by username: {e}")
            raise

    async def authenticate_user(self, email: str, password: str) -> UserInDB | None:
        """Authenticate user with email and password"""
        try:
            user = await self.get_user_by_email(email)
            if not user:
                return None

            if not verify_password(password, user.password):
                return None

            if not user.isActive:
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
            user = await User.find_one(User.id == ObjectId(user_id))
            if not user:
                return None

            update_data = user_update.dict(exclude_unset=True)
            if not update_data:
                return await self.get_user_by_id(user_id)

            # Update user fields
            for field, value in update_data.items():
                if hasattr(user, field):
                    setattr(user, field, value)

            user.updatedAt = datetime.now(UTC)
            await user.save()

            return await self.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise

    async def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        try:
            user = await User.find_one(User.id == ObjectId(user_id))
            if user:
                await user.delete()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            raise

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[UserInDB]:
        """List users with pagination"""
        try:
            cursor = User.find()
            users_docs = await cursor.skip(skip).limit(limit).to_list()
            users: list[UserInDB] = []
            for u in users_docs:
                users.append(
                    UserInDB(
                        id=u.id,
                        email=u.email,
                        phone=u.phone,
                        password=u.password,
                        userType=u.userType,
                        features=u.features,
                        firstName=u.firstName,
                        lastName=u.lastName,
                        address=u.address,
                        city=u.city,
                        pinCode=u.pinCode,
                        state=u.state,
                        organizationId=u.organizationId,
                        orgName=u.orgName,
                        isActive=u.isActive,
                        isVerified=u.isVerified,
                        createdAt=u.createdAt,
                        updatedAt=u.updatedAt,
                    )
                )
            return users
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            raise

    async def count_users(self) -> int:
        """Count total number of users"""
        try:
            return await User.count()
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            raise
