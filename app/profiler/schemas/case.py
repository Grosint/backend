"""Profiler case schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.utils.validators import PyObjectId


class CaseCreate(BaseModel):
    """Create a new profiler case."""

    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(None, max_length=2048)
    org_id: PyObjectId | None = Field(
        None, description="Optional; resolved from user when not provided"
    )


class CaseResponse(BaseModel):
    """Profiler case response."""

    id: str
    org_id: str
    name: str
    description: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
