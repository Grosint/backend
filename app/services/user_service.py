from __future__ import annotations

import logging
from datetime import UTC, datetime

from bson import ObjectId

from app.core.config import settings
from app.core.exceptions import ConflictException
from app.models.user import User, UserCreate, UserInDB, UserUpdate
from app.utils.password import hash_password, verify_password
from app.utils.validators import is_gov_email

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db):
        self.db = db
        self.collection = db[settings.MONGODB_COLLECTION_USERS]

    async def create_signup_user(self, email: str) -> UserInDB:
        """
        Create (or reuse) a minimal pre-OTP signup user.

        This supports the new signup flow where the user is created with only:
        - email
        - isGovId (derived from email domain)
        - required metadata (createdAt/updatedAt, isActive, etc.)

        A pending signup user is identified as one with:
        - matching email
        - phone is None
        - isEmailOtpVerified is False
        """
        normalized_email = email.lower().strip()

        # Reuse an existing pending user for this email to avoid multiple "pending" rows
        # and to keep OTP verification deterministic.
        pending_users = (
            await User.find(
                User.email == normalized_email,
                User.phone == None,  # noqa: E711 (Beanie query)
                User.isEmailOtpVerified == False,  # noqa: E712 (Beanie query)
            )
            .sort("-createdAt")
            .limit(1)
            .to_list()
        )

        if pending_users:
            user = pending_users[0]
            # Keep isGovId in sync with email domain patterns
            user.isGovId = is_gov_email(user.email)
            await user.save()
            return await self.get_user_by_id(str(user.id))

        new_user = User(
            email=normalized_email,
            phone=None,
            password=None,
            isGovId=is_gov_email(normalized_email),
            isEmailOtpVerified=False,
            isActive=True,
            isVerified=False,
        )
        await new_user.insert()

        logger.info(f"Pre-OTP signup user created: {normalized_email}")
        return await self.get_user_by_id(str(new_user.id))

    async def create_user(self, user: UserCreate) -> UserInDB:
        """Create a new user"""
        try:
            # Check if phone number already exists (phone must be unique when present)
            if user.phone is not None:
                existing_user = await User.find_one(User.phone == user.phone)
                if existing_user:
                    raise ConflictException(
                        message="User with this phone number already exists",
                        details={"phone": user.phone},
                    )

            # Create new user document
            new_user = User(
                email=user.email,
                phone=user.phone,
                password=hash_password(user.password) if user.password else None,
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
                isVerified=False,  # Will be set to True after OTP verification (gov IDs only)
                isGovId=(
                    user.isGovId
                    if user.isGovId is not None
                    else is_gov_email(user.email)
                ),
                isEmailOtpVerified=(
                    user.isEmailOtpVerified
                    if user.isEmailOtpVerified is not None
                    else False
                ),
            )
            await new_user.insert()

            user_type = user.userType.value if user.userType is not None else "None"
            logger.info(f"User created: {user.email}, type: {user_type}")
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
                    if field == "password":
                        setattr(user, field, hash_password(value) if value else None)
                    else:
                        setattr(user, field, value)

            user.updatedAt = datetime.now(UTC)
            await user.save()

            return await self.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            raise

    async def update_user_by_email_and_optional_phone(
        self,
        email: str,
        phone: str | None,
        user_update: UserUpdate,
        *,
        require_email_otp_verified: bool = True,
    ) -> UserInDB:
        """
        Update a user during "complete signup" flow using email (and phone when needed).

        Rules:
        - If exactly one user exists for email -> update that user.
        - If multiple users exist for email -> require phone to disambiguate.
          - If a user with (email, phone) exists -> update that one.
          - Otherwise, update the most recent "pending" user for email (phone is None),
            and set its phone to the provided value.
        - If require_email_otp_verified -> only allow update when isEmailOtpVerified is True.
        """
        normalized_email = email.lower().strip()
        users = await User.find(User.email == normalized_email).to_list()

        if not users:
            raise ConflictException(
                message="User not found for this email. Please start signup first.",
                details={"email": normalized_email},
            )

        target: User | None = None
        if len(users) == 1:
            target = users[0]
        else:
            if not phone:
                raise ConflictException(
                    message=(
                        "Multiple users found with this email. "
                        "Please provide phone number to update the correct user."
                    ),
                    details={"email": normalized_email, "user_count": len(users)},
                )

            normalized_phone = phone
            # Prefer exact match on email+phone
            target = await User.find_one(
                User.email == normalized_email, User.phone == normalized_phone
            )

            # If no exact match, fall back to most recent pending user (phone is None)
            if target is None:
                pending = (
                    await User.find(
                        User.email == normalized_email,
                        User.phone == None,  # noqa: E711
                    )
                    .sort("-createdAt")
                    .limit(1)
                    .to_list()
                )
                if pending:
                    target = pending[0]

        if target is None:
            raise ConflictException(
                message="Could not uniquely identify user to update.",
                details={"email": normalized_email},
            )

        if require_email_otp_verified and not target.isEmailOtpVerified:
            raise ConflictException(
                message="Email OTP not verified. Please verify OTP before completing signup.",
                details={"email": normalized_email},
            )

        # If caller provided phone and target doesn't have phone yet, set it (unique constraint will be enforced)
        update_data = user_update.dict(exclude_unset=True)
        if phone and not target.phone:
            # Enforce phone uniqueness across all users
            existing_user = await User.find_one(User.phone == phone)
            if existing_user and str(existing_user.id) != str(target.id):
                raise ConflictException(
                    message="User with this phone number already exists",
                    details={"phone": phone},
                )
            update_data["phone"] = phone

        for field, value in update_data.items():
            if hasattr(target, field):
                if field == "password":
                    setattr(target, field, hash_password(value) if value else None)
                else:
                    setattr(target, field, value)

        target.updatedAt = datetime.now(UTC)
        await target.save()
        return await self.get_user_by_id(str(target.id))

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
