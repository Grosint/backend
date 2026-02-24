"""ProfilerTarget Beanie document."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from beanie import Document, Insert, Replace, before_event
from pymongo import IndexModel

from app.utils.validators import PyObjectId

DetectedSource = Literal[
    "x", "instagram", "facebook", "google", "blog", "linkedin", "reddit", "unknown"
]
TargetType = Literal["url", "username"]


class ProfilerTarget(Document):
    """Profiler target - URL or username to capture."""

    case_id: PyObjectId
    org_id: PyObjectId
    created_by: PyObjectId
    target_type: TargetType
    input_value: str
    detected_source: DetectedSource
    canonical_url: str
    created_at: datetime | None = None

    @before_event([Insert, Replace])
    def set_timestamps(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(UTC)

    class Settings:
        name = "profiler_targets"
        indexes = [
            IndexModel([("org_id", 1), ("case_id", 1)], name="org_case_idx"),
            IndexModel([("canonical_url", 1)], name="canonical_url_idx"),
            IndexModel([("created_at", -1)], name="created_at_idx"),
        ]
