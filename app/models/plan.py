from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, Insert, Replace, before_event
from pydantic import Field


class Plan(Document):
    """Plan model for subscription and on-demand payment plans."""

    name: str
    cashfreePlanId: str | None = None
    price: int  # Price in paise (smallest currency unit)
    credits: int
    durationInDays: int  # Duration in days
    isPrepaid: bool = False  # True for ON_DEMAND, False for PERIODIC
    isActive: bool = True
    discount: int = 0  # Discount in paise
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "plans"
