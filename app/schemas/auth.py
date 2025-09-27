from __future__ import annotations

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """Token schema for response"""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data schema for decoded JWT payload"""

    username: str | None = None


class UserLogin(BaseModel):
    """User login request schema"""

    username: EmailStr
    password: str
