"""ProfileEntity - canonical profile from any source."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId


class ProfileEntity(Document):
    """Normalized profile entity across all sources."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    source: str
    source_id: str
    username: str
    display_name: str
    bio: str = ""
    follower_count: int | None = None
    verified: bool | None = None
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "profiler_entities_profiles"
        indexes = [
            IndexModel(
                [("org_id", 1), ("case_id", 1), ("target_id", 1)],
                name="org_case_target_idx",
            ),
            IndexModel(
                [("source", 1), ("source_id", 1)],
                name="source_source_id_idx",
            ),
        ]
