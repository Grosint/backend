"""Authentication dependencies and middleware."""

from datetime import UTC, datetime

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_database
from app.core.exceptions import AuthorizationException, UnauthorizedException
from app.core.token_blocklist import is_token_blocked
from app.models.user import User, UserType
from app.schemas.auth import AuthStatus, TokenInfo
from app.utils.jwt import get_token_jti, verify_access_token

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


class TokenData:
    """Token data container for authenticated users."""

    def __init__(self, user_id: str, email: str, token_type: str, expires_at: datetime):
        self.user_id = user_id
        self.email = email
        self.token_type = token_type
        self.expires_at = expires_at


def get_authorization_header(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str | None:
    """
    Extract authorization header from request.

    Args:
        credentials: HTTP authorization credentials

    Returns:
        Authorization header value or None
    """
    if not credentials:
        return None

    # Only accept Bearer scheme
    if credentials.scheme.lower() != "bearer":
        return None

    # HTTPBearer already extracts the token part, so credentials.credentials is the token
    token = credentials.credentials

    if not token:
        return None

    return token


async def verify_token_not_blocked(token: str, database) -> bool:
    """
    Verify token is not in blocklist.

    Args:
        token: JWT token to check
        database: Database instance

    Returns:
        True if token is not blocked

    Raises:
        UnauthorizedException: If token is blocked
    """
    try:
        jti = get_token_jti(token)
        if await is_token_blocked(jti, database):
            raise UnauthorizedException("Token has been revoked")
        return True
    except Exception as e:
        raise UnauthorizedException(f"Token verification failed: {str(e)}") from e


async def get_current_user_token(
    token: str | None = Depends(get_authorization_header),
    database=Depends(get_database),
) -> TokenData:
    """
    Get current user from JWT token.

    Args:
        token: JWT token from authorization header
        database: Database instance

    Returns:
        TokenData object with user information

    Raises:
        UnauthorizedException: If token is invalid, expired, or blocked
    """
    if not token:
        raise UnauthorizedException("Authorization header missing")

    try:
        # Verify token is not blocked (await async check)
        await verify_token_not_blocked(token, database)

        # Verify and decode token
        payload = verify_access_token(token)

        # Extract user information
        user_id = payload.get("sub")
        email = payload.get("email")
        token_type = payload.get("type")
        exp_timestamp = payload.get("exp")

        if not all([user_id, email, token_type, exp_timestamp]):
            raise UnauthorizedException("Invalid token payload")

        # Convert expiration timestamp to datetime
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=UTC)

        return TokenData(
            user_id=user_id, email=email, token_type=token_type, expires_at=expires_at
        )

    except Exception as e:
        raise UnauthorizedException(f"Authentication failed: {str(e)}") from e


def get_current_user_id(token_data: TokenData = Depends(get_current_user_token)) -> str:
    """
    Get current user ID from token data.

    Args:
        token_data: Token data from get_current_user_token

    Returns:
        User ID
    """
    return token_data.user_id


def get_current_user_email(
    token_data: TokenData = Depends(get_current_user_token),
) -> str:
    """
    Get current user email from token data.

    Args:
        token_data: Token data from get_current_user_token

    Returns:
        User email
    """
    return token_data.email


def get_auth_status(
    token_data: TokenData | None = Depends(get_current_user_token),
) -> AuthStatus:
    """
    Get authentication status.

    Args:
        token_data: Token data (optional, will be None if not authenticated)

    Returns:
        AuthStatus object
    """
    if token_data is None:
        return AuthStatus(
            is_authenticated=False,
            user_id=None,
            email=None,
            token_type=None,
            expires_at=None,
        )

    return AuthStatus(
        is_authenticated=True,
        user_id=token_data.user_id,
        email=token_data.email,
        token_type=token_data.token_type,
        expires_at=token_data.expires_at,
    )


async def get_token_info(
    token: str | None = Depends(get_authorization_header),
    database=Depends(get_database),
) -> TokenInfo | None:
    """
    Get detailed token information.

    Args:
        token: JWT token from authorization header
        database: Database instance

    Returns:
        TokenInfo object or None if no token
    """
    if not token:
        return None

    try:
        # Verify token is not blocked
        await verify_token_not_blocked(token, database)

        # Verify and decode token
        payload = verify_access_token(token)

        # Extract token information
        user_id = payload.get("sub")
        email = payload.get("email")
        token_type = payload.get("type")
        iat_timestamp = payload.get("iat")
        exp_timestamp = payload.get("exp")

        if not all([user_id, email, token_type, iat_timestamp, exp_timestamp]):
            return None

        # Convert timestamps to datetime
        issued_at = datetime.fromtimestamp(iat_timestamp, tz=UTC)
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=UTC)

        # Check if expired
        is_expired = datetime.now(UTC) > expires_at

        return TokenInfo(
            token_type=token_type,
            user_id=user_id,
            email=email,
            issued_at=issued_at,
            expires_at=expires_at,
            is_expired=is_expired,
        )

    except Exception:
        return None


# Optional authentication (doesn't raise exception if not authenticated)
def get_current_user_optional(
    token_data: TokenData | None = Depends(get_current_user_token),
) -> TokenData | None:
    """
    Get current user if authenticated, None otherwise.

    Args:
        token_data: Token data from get_current_user_token

    Returns:
        TokenData object or None if not authenticated
    """
    return token_data


async def get_current_user(
    token_data: TokenData = Depends(get_current_user_token),
    database=Depends(get_database),
) -> User:
    """
    Get current user document from database.

    Args:
        token_data: Token data from get_current_user_token
        database: Database instance

    Returns:
        User document

    Raises:
        UnauthorizedException: If user not found
    """
    try:
        from bson import ObjectId

        user = await User.find_one(User.id == ObjectId(token_data.user_id))
        if not user:
            raise UnauthorizedException("User not found")

        return user

    except Exception as e:
        raise UnauthorizedException(f"Failed to get user: {str(e)}") from e


async def require_user_type(
    *allowed_types: UserType,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require specific user type(s) for access.

    Args:
        *allowed_types: Allowed user types
        current_user: Current user document

    Returns:
        User document if user type is allowed

    Raises:
        AuthorizationException: If user type is not allowed
    """
    if not allowed_types:
        # If no types specified, allow all authenticated users
        return current_user

    if current_user.userType not in allowed_types:
        raise AuthorizationException(
            f"Access denied. Required user type(s): {', '.join(t.value for t in allowed_types)}"
        )

    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require admin user type for access.

    Args:
        current_user: Current user document

    Returns:
        User document if user is admin

    Raises:
        AuthorizationException: If user is not admin
    """
    if current_user.userType != UserType.ADMIN:
        raise AuthorizationException("Admin access required")

    return current_user


async def require_org_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require org_admin user type for access.

    Args:
        current_user: Current user document

    Returns:
        User document if user is org_admin

    Raises:
        AuthorizationException: If user is not org_admin
    """
    if current_user.userType != UserType.ORG_ADMIN:
        raise AuthorizationException("Organization admin access required")

    return current_user


async def require_feature(
    feature: str | None = None,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Require specific feature access.

    Args:
        feature: Feature name to check (e.g., "feature_a", "mobile360")
                 If None, allows all authenticated users
        current_user: Current user document

    Returns:
        User document if user has feature access

    Raises:
        AuthorizationException: If user doesn't have required feature access
    """
    # Admin users have all features
    if current_user.userType == UserType.ADMIN:
        return current_user

    # Org admin users have all features
    if current_user.userType == UserType.ORG_ADMIN:
        return current_user

    # If no feature specified, allow all authenticated users
    if feature is None:
        return current_user

    # Check if user has the required feature
    if feature not in current_user.features:
        raise AuthorizationException(f"Access denied. Required feature: {feature}")

    return current_user
