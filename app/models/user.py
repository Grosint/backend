from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from beanie import Document, Indexed, Insert, Replace, before_event
from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import (
    PyObjectId,
    validate_phone_number,
    validate_required_phone_number,
)


class UserType(str, Enum):
    """User type enumeration."""

    ADMIN = "admin"
    USER = "user"
    ORG_ADMIN = "org_admin"
    ORG_USER = "org_user"


class UserBase(BaseModel):
    email: EmailStr
    phone: str
    password: str
    userType: UserType = UserType.USER
    features: list[str] = Field(
        default_factory=list, description="List of feature access permissions"
    )
    firstName: str | None = None
    lastName: str | None = None
    address: str | None = None
    city: str | None = None
    pinCode: str | None = None
    state: str | None = None
    organizationId: PyObjectId | None = Field(
        None, description="Organization ID for org_user"
    )
    orgName: str | None = Field(None, description="Organization name for org_admin")
    isActive: bool = True
    isVerified: bool = False
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_required_phone_number(v)


class UserCreate(BaseModel):
    """Model for user creation - only required fields"""

    email: EmailStr
    phone: str
    password: str
    userType: UserType = UserType.USER
    firstName: str | None = None
    lastName: str | None = None
    address: str | None = None
    city: str | None = None
    pinCode: str | None = None
    state: str | None = None
    organizationId: PyObjectId | None = None
    orgName: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_required_phone_number(v)


class UserUpdate(BaseModel):
    """Model for user updates - all fields optional"""

    email: EmailStr | None = None
    phone: str | None = None
    userType: UserType | None = None
    features: list[str] | None = None
    firstName: str | None = None
    lastName: str | None = None
    address: str | None = None
    city: str | None = None
    pinCode: str | None = None
    state: str | None = None
    organizationId: PyObjectId | None = None
    orgName: str | None = None
    isActive: bool | None = None
    isVerified: bool | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_phone_number(v)


class UserInDB(UserBase):
    id: PyObjectId = None
    password: str

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class User(Document):
    email: Indexed(EmailStr, unique=True)
    phone: str
    password: str
    userType: UserType = UserType.USER
    features: list[str] = Field(
        default_factory=list, description="List of feature access permissions"
    )
    firstName: str | None = None
    lastName: str | None = None
    address: str | None = None
    city: str | None = None
    pinCode: str | None = None
    state: str | None = None
    organizationId: PyObjectId | None = Field(
        None, description="Organization ID for org_user"
    )
    orgName: str | None = Field(None, description="Organization name for org_admin")
    isActive: bool = True
    isVerified: bool = False
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_phone_number(v)

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "users"
        indexes = [
            [("organizationId", 1)],  # Index for organization queries
            [("userType", 1)],  # Index for user type queries
        ]
