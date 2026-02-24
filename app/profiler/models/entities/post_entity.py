"""PostEntity - canonical post from any source."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId


class PostEntity(Document):
    """Normalized post entity across all sources."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    source: str
    source_post_id: str
    author_profile_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    text_content: str | None = None
    media_ids: list[str] = Field(default_factory=list)
    location_id: str | None = None
    engagement_counts: dict = Field(default_factory=dict)
    evidence_id: str

    class Settings:
        name = "profiler_entities_posts"
        indexes = [
            IndexModel(
                [("target_id", 1), ("created_at", -1)],
                name="target_created_idx",
            ),
            IndexModel(
                [("source", 1), ("source_post_id", 1)],
                name="source_post_id_idx",
            ),
        ]
