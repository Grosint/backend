from __future__ import annotations

import re
from datetime import UTC, datetime

from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


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


class UserCreate(BaseModel):
    """Model for user creation - only required fields"""

    email: EmailStr
    phone: str
    verifyByGovId: bool
    password: str

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


class UserInDB(UserBase):
    id: PyObjectId = None
    password: str

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class User(UserBase):
    id: PyObjectId = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
