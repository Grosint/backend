"""MediaEntity - canonical media from any source."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId

MediaType = Literal["image", "video"]


class MediaEntity(Document):
    """Normalized media entity across all sources."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    source: str
    source_media_id: str
    media_type: MediaType
    blob_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sha256: str
    evidence_id: str

    class Settings:
        name = "profiler_entities_media"
        indexes = [
            IndexModel(
                [("target_id", 1), ("created_at", -1)],
                name="target_created_idx",
            ),
        ]
