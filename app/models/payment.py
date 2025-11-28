from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, Insert, Replace, before_event
from pydantic import Field

from app.utils.validators import PyObjectId


class PaymentStatus:
    """Payment status constants."""

    PENDING = "pending"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    COMPLETED = "completed"
    FAILED = "failed"


class Payment(Document):
    """Payment transaction model."""

    userId: PyObjectId
    planId: PyObjectId | None = None  # Plan ID for credit activation
    subscriptionId: PyObjectId | None = None
    cfPaymentId: str
    cfOrderId: str
    amount: float  # Amount in rupees
    status: str = Field(
        default=PaymentStatus.PENDING,
        description="Payment status: pending, cancelled, expired, completed, failed",
    )
    paymentMethod: str | None = None
    transactionTime: datetime | None = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "payments"
