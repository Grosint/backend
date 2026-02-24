"""Profiler artifact schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ArtifactType = Literal[
    "profile_card",
    "timeline",
    "coverage",
    "engagement",
    "hashtags",
    "locations",
    "inference_result",
]


class ArtifactResponse(BaseModel):
    """Profiler artifact response."""

    id: str
    org_id: str
    case_id: str
    target_id: str
    job_id: str
    artifact_type: ArtifactType
    version: str
    payload: dict
    evidence_ids: list[str]
    created_at: datetime
