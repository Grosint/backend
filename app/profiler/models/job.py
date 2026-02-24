"""ProfilerJob Beanie document."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from beanie import Document, Insert, Replace, before_event
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId

JobType = Literal["public_capture", "normalize", "analyze", "inference"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "not_collectible"]


class ProfilerJob(Document):
    """Profiler job - capture or inference task."""

    case_id: PyObjectId
    target_id: PyObjectId
    org_id: PyObjectId
    created_by: PyObjectId
    job_type: JobType
    status: JobStatus = "queued"
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    idempotency_key: str = ""
    payload: dict | None = None
    checkpoint: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    error: dict | None = None

    @before_event([Insert, Replace])
    def ensure_created_at(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(UTC)

    class Settings:
        name = "profiler_jobs"
        indexes = [
            IndexModel([("org_id", 1)], name="org_id_idx"),
            IndexModel([("case_id", 1)], name="case_id_idx"),
            IndexModel([("target_id", 1)], name="target_id_idx"),
            IndexModel([("status", 1)], name="status_idx"),
            IndexModel([("created_at", -1)], name="created_at_idx"),
            IndexModel([("idempotency_key", 1)], name="idempotency_key_idx"),
        ]
