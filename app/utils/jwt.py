"""JWT token utilities with security best practices."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import PyJWTError

from app.core.config import settings


class JWTManager:
    """JWT token manager with security best practices."""

    # Token types for different purposes
    ACCESS_TOKEN_TYPE = "access"
    REFRESH_TOKEN_TYPE = "refresh"

    # Token expiration times (following OAuth 2.0 best practices)
    ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived access tokens
    REFRESH_TOKEN_EXPIRE_DAYS = 7  # Longer-lived refresh tokens

    def __init__(self):
        """Initialize JWT manager with secure settings."""
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"  # Recommended for HMAC
        self.issuer = "grosint-backend"
        self.audience = "grosint-users"

    def _create_token_payload(
        self,
        user_id: str,
        email: str,
        token_type: str,
        expires_delta: timedelta | None = None,
        additional_claims: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create secure JWT payload following best practices.

        Args:
            user_id: User's unique identifier
            email: User's email address
            token_type: Type of token (access/refresh)
            expires_delta: Custom expiration time
            additional_claims: Additional claims to include

        Returns:
            JWT payload dictionary
        """
        now = datetime.now(UTC)

        # Standard JWT claims (RFC 7519)
        payload = {
            # Issued at
            "iat": now,
            # Expiration time
            "exp": now + (expires_delta or self._get_default_expiry(token_type)),
            # Issuer
            "iss": self.issuer,
            # Audience
            "aud": self.audience,
            # Subject (user ID)
            "sub": user_id,
            # Token type
            "type": token_type,
            # User email
            "email": email,
            # JWT ID (unique token identifier)
            "jti": secrets.token_urlsafe(32),
            # Not before (prevents replay attacks)
            "nbf": now,
        }

        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)

        return payload

    def _get_default_expiry(self, token_type: str) -> timedelta:
        """Get default expiration time based on token type."""
        if token_type == self.ACCESS_TOKEN_TYPE:
            return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        elif token_type == self.REFRESH_TOKEN_TYPE:
            return timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        else:
            raise ValueError(f"Unknown token type: {token_type}")

    def create_access_token(
        self,
        user_id: str,
        email: str,
        expires_delta: timedelta | None = None,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """
        Create access token for API authentication.

        Args:
            user_id: User's unique identifier
            email: User's email address
            expires_delta: Custom expiration time
            additional_claims: Additional claims (roles, permissions, etc.)

        Returns:
            Encoded JWT access token
        """
        payload = self._create_token_payload(
            user_id=user_id,
            email=email,
            token_type=self.ACCESS_TOKEN_TYPE,
            expires_delta=expires_delta,
            additional_claims=additional_claims,
        )

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self, user_id: str, email: str, expires_delta: timedelta | None = None
    ) -> str:
        """
        Create refresh token for obtaining new access tokens.

        Args:
            user_id: User's unique identifier
            email: User's email address
            expires_delta: Custom expiration time

        Returns:
            Encoded JWT refresh token
        """
        payload = self._create_token_payload(
            user_id=user_id,
            email=email,
            token_type=self.REFRESH_TOKEN_TYPE,
            expires_delta=expires_delta,
        )

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(
        self, token: str, token_type: str = ACCESS_TOKEN_TYPE
    ) -> dict[str, Any]:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token to verify
            token_type: Expected token type

        Returns:
            Decoded token payload

        Raises:
            PyJWTError: If token is invalid, expired, or malformed
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )

            # Verify token type
            if payload.get("type") != token_type:
                raise PyJWTError(f"Invalid token type. Expected: {token_type}")

            return payload

        except PyJWTError as e:
            raise PyJWTError(f"Token verification failed: {str(e)}") from e

    def extract_user_id(self, token: str) -> str:
        """
        Extract user ID from token.

        Args:
            token: JWT token

        Returns:
            User ID

        Raises:
            PyJWTError: If token is invalid
        """
        payload = self.verify_token(token)
        return payload.get("sub")

    def extract_user_email(self, token: str) -> str:
        """
        Extract user email from token.

        Args:
            token: JWT token

        Returns:
            User email

        Raises:
            PyJWTError: If token is invalid
        """
        payload = self.verify_token(token)
        return payload.get("email")

    def get_token_jti(self, token: str) -> str:
        """
        Get JWT ID from token for blocklist management.

        Args:
            token: JWT token

        Returns:
            JWT ID

        Raises:
            PyJWTError: If token is invalid
        """
        payload = self.verify_token(token)
        return payload.get("jti")

    def is_token_expired(self, token: str) -> bool:
        """
        Check if token is expired without raising exception.

        Args:
            token: JWT token

        Returns:
            True if expired, False otherwise
        """
        try:
            self.verify_token(token)
            return False
        except PyJWTError:
            return True

    def get_token_expiry(self, token: str) -> datetime | None:
        """
        Get token expiration time.

        Args:
            token: JWT token

        Returns:
            Expiration datetime or None if invalid
        """
        try:
            payload = self.verify_token(token)
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp, tz=UTC)
        except PyJWTError:
            pass
        return None


# Global JWT manager instance
jwt_manager = JWTManager()


# Convenience functions
def create_access_token(
    user_id: str,
    email: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create access token."""
    return jwt_manager.create_access_token(
        user_id, email, expires_delta, additional_claims
    )


def create_refresh_token(
    user_id: str, email: str, expires_delta: timedelta | None = None
) -> str:
    """Create refresh token."""
    return jwt_manager.create_refresh_token(user_id, email, expires_delta)


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify access token."""
    return jwt_manager.verify_token(token, JWTManager.ACCESS_TOKEN_TYPE)


def verify_refresh_token(token: str) -> dict[str, Any]:
    """Verify refresh token."""
    return jwt_manager.verify_token(token, JWTManager.REFRESH_TOKEN_TYPE)


def get_current_user_id(token: str) -> str:
    """Get current user ID from token."""
    return jwt_manager.extract_user_id(token)


def get_current_user_email(token: str) -> str:
    """Get current user email from token."""
    return jwt_manager.extract_user_email(token)


def get_token_jti(token: str) -> str:
    """Get token JTI for blocklist management."""
    return jwt_manager.get_token_jti(token)
