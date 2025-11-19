from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from beanie import Document, Indexed, Insert, Replace, before_event
from pydantic import BaseModel, Field

from app.utils.validators import PyObjectId


class ResultCreate(BaseModel):
    """Model for creating a new result"""

    search_id: PyObjectId
    source: str
    data: dict[str, Any]
    confidence_score: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResultUpdate(BaseModel):
    """Model for updating an existing result"""

    data: dict[str, Any] | None = None
    confidence_score: float | None = None


class Result(Document):
    """Result document model"""

    search_id: Indexed(PyObjectId)
    source: str
    data: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now

    class Settings:
        name = "results"
        indexes = [
            "search_id",
            "source",
            [
                ("created_at", -1),
            ],
        ]
