"""ProfilerArtifact Beanie document."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from beanie import Document, Insert, Replace, before_event
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId

ArtifactType = Literal[
    "profile_card",
    "timeline",
    "coverage",
    "engagement",
    "hashtags",
    "locations",
    "activity",
    "comments_summary",
    "photos_summary",
    "lifestyle",
    "beliefs",
    "inference_result",
]


class ProfilerArtifact(Document):
    """Profiler artifact - derived/computed output from source documents."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    job_id: PyObjectId
    artifact_type: ArtifactType
    version: str = "v1"
    payload: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def ensure_created_at(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(UTC)

    class Settings:
        name = "profiler_artifacts"
        indexes = [
            IndexModel([("org_id", 1)], name="org_id_idx"),
            IndexModel([("case_id", 1)], name="case_id_idx"),
            IndexModel([("target_id", 1)], name="target_id_idx"),
            IndexModel([("artifact_type", 1)], name="artifact_type_idx"),
            IndexModel([("created_at", -1)], name="created_at_idx"),
        ]
