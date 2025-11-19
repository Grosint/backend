from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from beanie import Document, Indexed, Insert, Replace, before_event
from pydantic import BaseModel, Field

from app.utils.validators import PyObjectId


class SearchType(str, Enum):
    """Enum for search types"""

    EMAIL = "email"
    DOMAIN = "domain"
    PHONE = "phone"
    USERNAME = "username"


class SearchStatus(str, Enum):
    """Enum for search status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SearchCreate(BaseModel):
    """Model for creating a new search"""

    user_id: PyObjectId | None = None
    search_type: SearchType
    query: str
    status: SearchStatus = SearchStatus.PENDING


class SearchUpdate(BaseModel):
    """Model for updating an existing search"""

    status: SearchStatus | None = None
    results_count: int | None = None
    error_message: str | None = None


class Search(Document):
    """Search document model"""

    user_id: Indexed(PyObjectId) | None = None
    search_type: SearchType
    query: str
    status: SearchStatus = SearchStatus.PENDING
    results_count: int = 0
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.created_at is None:
            self.created_at = now
        self.updated_at = now

    class Settings:
        name = "searches"
        indexes = [
            "user_id",
            "search_type",
            "status",
            [
                ("created_at", -1),
            ],
        ]
