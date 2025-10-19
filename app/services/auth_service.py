"""Authentication service for user login/logout operations."""

from datetime import UTC, datetime

from bson import ObjectId

from app.core.exceptions import NotFoundException, UnauthorizedException
from app.core.token_blocklist import add_token_to_blocklist
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshTokenResponse,
)
from app.utils.jwt import (
    create_access_token,
    create_refresh_token,
    get_current_user_id,
    get_token_jti,
    jwt_manager,
)
from app.utils.password import hash_password, verify_password


class AuthService:
    """Authentication service for user operations."""

    def __init__(self, database):
        """Initialize auth service with database connection."""
        self.database = database

    async def authenticate_user(self, email: str, password: str) -> User | None:
        """
        Authenticate user with email and password.

        Args:
            email: User email
            password: User password

        Returns:
            User object if authentication successful, None otherwise
        """
        try:
            # Find user by email
            user = await self._find_user_by_email(email)

            if not user:
                return None

            # Check if user is active
            if not user.isActive:
                return None

            # Verify password
            if not verify_password(password, user.password):
                return None

            return user

        except Exception as e:
            print(f"Error authenticating user: {e}")
            return None

    async def _find_user_by_email(self, email: str) -> User | None:
        """Find user by email. This method can be overridden in tests."""
        return await User.find_one(User.email == email)

    async def _find_user_by_id(self, user_id: str) -> User | None:
        """Find user by ID. This method can be overridden in tests."""
        return await User.find_one(User.id == ObjectId(user_id))

    async def login(self, login_request: LoginRequest) -> LoginResponse:
        """
        Authenticate user and create tokens.

        Args:
            login_request: Login request data

        Returns:
            Login response with tokens

        Raises:
            UnauthorizedException: If authentication fails
        """
        # Authenticate user
        user = await self.authenticate_user(login_request.email, login_request.password)

        if not user:
            raise UnauthorizedException("Invalid email or password")

        # Check if user is active
        if not user.isActive:
            raise UnauthorizedException("Account is deactivated")

        # Create tokens
        access_token = create_access_token(user_id=str(user.id), email=user.email)

        refresh_token = create_refresh_token(user_id=str(user.id), email=user.email)

        # Calculate expiration time
        expires_in = 15 * 60  # 15 minutes in seconds

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            user_id=str(user.id),
            email=user.email,
        )

    async def refresh_access_token(self, refresh_token: str) -> RefreshTokenResponse:
        """
        Create new access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New access token response

        Raises:
            UnauthorizedException: If refresh token is invalid
        """
        try:
            from app.utils.jwt import verify_refresh_token

            # Verify refresh token
            payload = verify_refresh_token(refresh_token)
            user_id = payload.get("sub")
            email = payload.get("email")

            if not user_id or not email:
                raise UnauthorizedException("Invalid refresh token")

            # Check if user still exists and is active
            user = await self._find_user_by_id(user_id)
            if not user or not user.isActive:
                raise UnauthorizedException("User not found or inactive")

            # Create new access token
            access_token = create_access_token(user_id=user_id, email=email)

            # Calculate expiration time
            expires_in = 15 * 60  # 15 minutes in seconds

            return RefreshTokenResponse(
                access_token=access_token, token_type="bearer", expires_in=expires_in
            )

        except Exception as e:
            raise UnauthorizedException(f"Token refresh failed: {str(e)}") from e

    async def logout(
        self, access_token: str, refresh_token: str | None = None
    ) -> LogoutResponse:
        """
        Logout user and invalidate tokens.

        Args:
            access_token: Access token to invalidate
            refresh_token: Refresh token to invalidate (optional)

        Returns:
            Logout response

        Raises:
            UnauthorizedException: If token is invalid
        """
        try:
            # Get token JTI for blocklist
            access_jti = get_token_jti(access_token)
            access_expiry = jwt_manager.get_token_expiry(access_token)

            # Get user ID from token
            from app.utils.jwt import get_current_user_id

            user_id = get_current_user_id(access_token)

            # Add access token to blocklist
            await add_token_to_blocklist(
                jti=access_jti,
                user_id=user_id,
                token_type="access",
                expires_at=access_expiry,
                reason="logout",
                database=self.database,
            )

            # Add refresh token to blocklist if provided
            if refresh_token:
                try:
                    refresh_jti = get_token_jti(refresh_token)
                    refresh_expiry = jwt_manager.get_token_expiry(refresh_token)

                    await add_token_to_blocklist(
                        jti=refresh_jti,
                        user_id=user_id,
                        token_type="refresh",
                        expires_at=refresh_expiry,
                        reason="logout",
                        database=self.database,
                    )
                except Exception:
                    # If refresh token is invalid, continue with access token logout
                    pass

            return LogoutResponse(
                message="Successfully logged out", logged_out_at=datetime.now(UTC)
            )

        except Exception as e:
            raise UnauthorizedException(f"Logout failed: {str(e)}") from e

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> bool:
        """
        Change user password.

        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password

        Returns:
            True if password changed successfully

        Raises:
            UnauthorizedException: If current password is incorrect
            NotFoundException: If user not found
        """
        try:
            # Find user
            user = await self._find_user_by_id(user_id)
            if not user:
                raise NotFoundException("User not found")

            # Verify current password
            if not verify_password(current_password, user.password):
                raise UnauthorizedException("Current password is incorrect")

            # Hash new password
            hashed_password = hash_password(new_password)

            # Update user password
            user.password = hashed_password
            await user.save()

            return True

        except Exception as e:
            if isinstance(e, UnauthorizedException | NotFoundException):
                raise
            raise UnauthorizedException(f"Password change failed: {str(e)}") from e

    async def get_user_by_token(self, token: str) -> User | None:
        """
        Get user from token.

        Args:
            token: JWT token

        Returns:
            User object or None if not found
        """
        try:
            user_id = get_current_user_id(token)
            user = await self._find_user_by_id(user_id)
            return user

        except Exception:
            return None

    async def validate_user_session(self, user_id: str) -> bool:
        """
        Validate user session is still active.

        Args:
            user_id: User ID to validate

        Returns:
            True if user session is valid
        """
        try:
            user = await self._find_user_by_id(user_id)
            return user is not None and user.isActive

        except Exception:
            return False
