"""Profiler job schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

JobType = Literal["public_capture", "inference"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "not_collectible"]


class JobResponse(BaseModel):
    """Profiler job response."""

    id: str
    case_id: str
    target_id: str
    org_id: str
    created_by: str
    job_type: JobType
    status: JobStatus
    attempts: int
    max_attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: dict | None
    metrics: dict
