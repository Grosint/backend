from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import validate_phone_number, validate_required_phone_number


class UserCreateRequest(BaseModel):
    """Request schema for user creation - only required fields"""

    email: EmailStr
    phone: str = Field(..., description="Phone number in E.164 format")
    verifyByGovId: bool
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_required_phone_number(v)


class UserUpdateRequest(BaseModel):
    """Request schema for user updates - all fields optional"""

    email: EmailStr | None = None
    phone: str | None = Field(None, description="Phone number in E.164 format")
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
        return validate_phone_number(v)


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
