"""Profiler target schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DetectedSource = Literal[
    "x", "instagram", "facebook", "blog", "linkedin", "reddit", "unknown"
]
TargetType = Literal["url", "username"]


class TargetCreate(BaseModel):
    """Create a new profiler target."""

    target_type: TargetType
    input_value: str = Field(..., min_length=1, max_length=2048)


class TargetResponse(BaseModel):
    """Profiler target response."""

    id: str
    case_id: str
    org_id: str
    created_by: str
    target_type: TargetType
    input_value: str
    detected_source: DetectedSource
    canonical_url: str
    created_at: datetime
