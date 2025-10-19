from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, Indexed, Insert, Replace, before_event
from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import (
    PyObjectId,
    validate_phone_number,
    validate_required_phone_number,
)


class UserBase(BaseModel):
    email: EmailStr
    phone: str
    password: str
    firstName: str | None = None
    lastName: str | None = None
    pinCode: str | None = None
    state: str | None = None
    isActive: bool = True
    verifyByGovId: bool = False
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
    verifyByGovId: bool
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        return validate_required_phone_number(v)


class UserUpdate(BaseModel):
    """Model for user updates - all fields optional"""

    email: EmailStr | None = None
    phone: str | None = None
    verifyByGovId: bool | None = None
    firstName: str | None = None
    lastName: str | None = None
    pinCode: str | None = None
    state: str | None = None
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
    firstName: str | None = None
    lastName: str | None = None
    pinCode: str | None = None
    state: str | None = None
    isActive: bool = True
    verifyByGovId: bool = False
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
