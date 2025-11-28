from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, Insert, Replace, before_event
from pydantic import Field

from app.utils.validators import PyObjectId


class CreditType:
    """Credit type constants."""

    ON_DEMAND = "ON_DEMAND"
    PERIODIC = "PERIODIC"


class CreditStatus:
    """Credit status constants."""

    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


class Credit(Document):
    """Credit model for user credits."""

    userId: PyObjectId
    type: str = Field(
        description="Credit type: ON_DEMAND or PERIODIC",
    )
    credits: int
    expiresAt: datetime | None = None
    status: str = Field(
        default=CreditStatus.ACTIVE,
        description="Credit status: ACTIVE or EXPIRED",
    )
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "credits"
