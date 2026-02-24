"""TagEntity - canonical tag/hashtag from any source."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId


class TagEntity(Document):
    """Normalized tag/hashtag entity across all sources."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    source: str
    tag: str
    post_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "profiler_entities_tags"
        indexes = [
            IndexModel([("target_id", 1)], name="target_id_idx"),
            IndexModel([("tag", 1)], name="tag_idx"),
        ]
