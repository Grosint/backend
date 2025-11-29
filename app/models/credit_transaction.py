from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, Insert, Replace, before_event
from pydantic import Field

from app.utils.validators import PyObjectId


class TransactionType:
    """Transaction type constants."""

    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class CreditTransaction(Document):
    """Credit transaction model for audit trail."""

    userId: PyObjectId
    creditsId: PyObjectId
    txnType: str = Field(
        description="Transaction type: CREDIT or DEBIT",
    )
    creditsUsed: int
    service: str | None = None  # Service that triggered the transaction
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "credit_transactions"
