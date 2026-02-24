"""CommentEntity - canonical comment from any source."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId


class CommentEntity(Document):
    """Normalized comment entity across all sources."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    source: str
    source_comment_id: str
    parent_post_id: str
    author_profile_id: str
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_id: str

    class Settings:
        name = "profiler_entities_comments"
        indexes = [
            IndexModel([("parent_post_id", 1)], name="parent_post_idx"),
            IndexModel([("created_at", -1)], name="created_at_idx"),
        ]
