"""ReviewEntity - canonical review from any source."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId


class ReviewEntity(Document):
    """Normalized review entity (e.g., Google Maps reviews)."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    place_name: str
    category: str = ""
    rating: float | None = None
    price_range: str | None = None
    review_text: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    location_id: str | None = None
    evidence_id: str

    class Settings:
        name = "profiler_entities_reviews"
        indexes = [
            IndexModel([("target_id", 1)], name="target_id_idx"),
            IndexModel([("created_at", -1)], name="created_at_idx"),
        ]
