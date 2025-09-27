from __future__ import annotations

import re
from datetime import UTC, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreateRequest(BaseModel):
    """Request schema for user creation - only required fields"""

    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=20)
    verifyByGovId: bool
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v

        # Remove all non-digit characters except +
        if v.startswith("+"):
            phone_digits = re.sub(r"\D", "", v[1:])  # Remove + and non-digits
        else:
            phone_digits = re.sub(r"\D", "", v)  # Remove all non-digits

        # Check if it's a valid length (7-15 digits)
        if len(phone_digits) < 7 or len(phone_digits) > 15:
            raise ValueError("Phone number must be between 7 and 15 digits")

        # Return in E.164 format if it doesn't start with +
        if not v.startswith("+") and phone_digits:
            return f"+{phone_digits}"

        return v


class UserUpdateRequest(BaseModel):
    """Request schema for user updates - all fields optional"""

    email: EmailStr | None = None
    phone: str | None = Field(None, min_length=7, max_length=20)
    verifyByGovId: bool | None = None
    firstName: str | None = Field(None, max_length=100)
    lastName: str | None = Field(None, max_length=100)
    pinCode: str | None = Field(None, max_length=10)
    state: str | None = Field(None, max_length=100)
    isActive: bool | None = None
    isVerified: bool | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v

        # Remove all non-digit characters except +
        if v.startswith("+"):
            phone_digits = re.sub(r"\D", "", v[1:])  # Remove + and non-digits
        else:
            phone_digits = re.sub(r"\D", "", v)  # Remove all non-digits

        # Check if it's a valid length (7-15 digits)
        if len(phone_digits) < 7 or len(phone_digits) > 15:
            raise ValueError("Phone number must be between 7 and 15 digits")

        # Return in E.164 format if it doesn't start with +
        if not v.startswith("+") and phone_digits:
            return f"+{phone_digits}"

        return v


class UserResponse(BaseModel):
    """Response schema for user data"""

    id: str
    email: str
    phone: str
    verifyByGovId: bool
    firstName: str | None = None
    lastName: str | None = None
    pinCode: str | None = None
    state: str | None = None
    isActive: bool
    isVerified: bool
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserListResponse(BaseModel):
    """Response schema for user list"""

    users: list[UserResponse]
    total: int
    page: int
    size: int


class UserCreateResponse(BaseModel):
    """Response schema for user creation"""

    message: str
    user_id: str
    user: UserResponse
