from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, Insert, Replace, before_event
from pydantic import Field

from app.utils.validators import PyObjectId


class SubscriptionStatus:
    """Subscription status constants."""

    INITIALIZED = "initialized"
    PENDING = "pending"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Subscription(Document):
    """Subscription model for periodic payment plans."""

    userId: PyObjectId
    planId: PyObjectId
    cfSubscriptionId: str | None = None
    status: str = Field(
        default=SubscriptionStatus.INITIALIZED,
        description="Subscription status: initialized, pending, active, cancelled, expired",
    )
    startDate: datetime | None = None
    nextBillingDate: datetime | None = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "subscriptions"
