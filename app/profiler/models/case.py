"""ProfilerCase Beanie document."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, Insert, Replace, before_event
from pymongo import IndexModel

from app.utils.validators import PyObjectId


class ProfilerCase(Document):
    """Profiler case - container for targets and collection jobs."""

    org_id: PyObjectId
    name: str
    description: str | None = None
    created_by: PyObjectId
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @before_event([Insert, Replace])
    def set_timestamps(self) -> None:
        now = datetime.now(UTC)
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now

    class Settings:
        name = "profiler_cases"
        indexes = [
            IndexModel([("org_id", 1)], name="org_id_idx"),
            IndexModel([("created_at", -1)], name="created_at_idx"),
        ]
