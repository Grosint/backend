"""Validation utilities and types used across the application."""

import re
from typing import Any

from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic models."""

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


def validate_phone_number(value: Any) -> str | None:
    """
    Validate and normalize phone number to E.164 format (for optional fields).

    Args:
        value: The phone number to validate (can be None for optional fields)

    Returns:
        Normalized phone number in E.164 format or None if input is None

    Raises:
        ValueError: If phone number is invalid
    """
    if value is None:
        return None

    # Handle empty string - this should be treated as invalid
    if value == "":
        raise ValueError("Phone number cannot be empty")

    # Check for multiple plus signs (invalid)
    if value.count("+") > 1:
        raise ValueError("Phone number cannot contain multiple plus signs")

    # Remove all non-digit characters except +
    if value.startswith("+"):
        phone_digits = re.sub(r"\D", "", value[1:])  # Remove + and non-digits
    else:
        phone_digits = re.sub(r"\D", "", value)  # Remove all non-digits

    # Check if it's a valid length (7-15 digits)
    if len(phone_digits) < 7 or len(phone_digits) > 15:
        raise ValueError("Phone number must be between 7 and 15 digits")

    # Always return in E.164 format
    return f"+{phone_digits}"


def validate_required_phone_number(value: Any) -> str:
    """
    Validate and normalize phone number to E.164 format (for required fields).

    Args:
        value: The phone number to validate (cannot be None)

    Returns:
        Normalized phone number in E.164 format

    Raises:
        ValueError: If phone number is invalid or missing
    """
    if value is None:
        raise ValueError("Phone number is required")

    # Handle empty string - this should be treated as invalid
    if value == "":
        raise ValueError("Phone number cannot be empty")

    # Check for multiple plus signs (invalid)
    if value.count("+") > 1:
        raise ValueError("Phone number cannot contain multiple plus signs")

    # Remove all non-digit characters except +
    if value.startswith("+"):
        phone_digits = re.sub(r"\D", "", value[1:])  # Remove + and non-digits
    else:
        phone_digits = re.sub(r"\D", "", value)  # Remove all non-digits

    # Check if it's a valid length (7-15 digits)
    if len(phone_digits) < 7 or len(phone_digits) > 15:
        raise ValueError("Phone number must be between 7 and 15 digits")

    # Always return in E.164 format
    return f"+{phone_digits}"


def is_gov_email(email: str) -> bool:
    """
    Detect if email is a government email based on domain patterns.

    Args:
        email: Email address to check

    Returns:
        True if email appears to be a government email
    """
    if not email:
        return False

    # Common government email domain patterns
    gov_patterns = [
        r"\.gov\.",  # .gov.
        r"\.gov\.in",  # .gov.in
        r"\.nic\.in",  # .nic.in
        r"@gov\.",  # @gov.
        r"@nic\.",  # @nic.
        r"@.*\.gov\.",  # @*.gov.
        r"@.*\.gov\.in",  # @*.gov.in
        r"@.*\.nic\.in",  # @*.nic.in
    ]

    email_lower = email.lower()

    return any(re.search(pattern, email_lower) for pattern in gov_patterns)
