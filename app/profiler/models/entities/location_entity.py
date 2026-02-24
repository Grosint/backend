"""LocationEntity - canonical location from any source."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId


class LocationEntity(Document):
    """Normalized location entity across all sources."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    source: str
    location_name: str
    lat: float | None = None
    lng: float | None = None
    country_code: str | None = None
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_ids: list[str] = Field(default_factory=list)

    class Settings:
        name = "profiler_entities_locations"
        indexes = [
            IndexModel([("target_id", 1)], name="target_id_idx"),
            IndexModel([("country_code", 1)], name="country_code_idx"),
        ]
