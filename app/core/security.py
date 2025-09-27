from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import settings
from app.schemas.auth import TokenData

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

# Logger
logger = logging.getLogger(__name__)

# In-memory rate limiting store
# In production, use Redis or similar for distributed deployments
rate_limit_store = defaultdict(list)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password for storing"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()

    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """Decode and validate JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # Create token data
        token_data = TokenData(username=username)
        return token_data

    except JWTError as e:
        logger.warning("JWT validation failed")
        raise credentials_exception from e


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests"""

    async def dispatch(self, request: Request, call_next):
        # Get client IP address
        client_ip = request.client.host

        # Clean up old request timestamps (older than 1 minute)
        current_time = time.time()
        rate_limit_store[client_ip] = [
            timestamp
            for timestamp in rate_limit_store[client_ip]
            if current_time - timestamp < 60
        ]

        # Check if rate limit exceeded
        if len(rate_limit_store[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return Response(
                content='{"detail":"Too many requests"}',
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )

        # Add current request timestamp
        rate_limit_store[client_ip].append(current_time)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(
            settings.RATE_LIMIT_PER_MINUTE - len(rate_limit_store[client_ip])
        )

        return response


async def add_security_headers(request: Request, call_next):
    """Add security headers to responses"""
    response = await call_next(request)

    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = "default-src 'self'"

    return response
