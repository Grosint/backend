from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from beanie import Document, Indexed, Insert, Replace, before_event
from pydantic import BaseModel, Field

from app.utils.validators import PyObjectId


class HistorySourceResult(BaseModel):
    source: str
    success: bool
    latencyMs: int | None = None
    data: dict[str, Any] | None = None
    errorCode: str | None = None
    message: str | None = None


class HistoryMetadata(BaseModel):
    totalSources: int = 0
    successfulSources: int = 0
    failedSources: int = 0
    startedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completedAt: datetime | None = None
    durationMs: int | None = None


class History(Document):
    userId: Indexed(PyObjectId) | None = None
    queryType: str
    queryInput: dict[str, Any] | str
    status: str = "IN_PROGRESS"  # IN_PROGRESS | COMPLETED | PARTIAL | FAILED
    results: list[HistorySourceResult] = Field(default_factory=list)
    metadata: HistoryMetadata = Field(default_factory=HistoryMetadata)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "histories"
        indexes = [
            "userId",
            [
                ("createdAt", -1),
            ],
        ]
