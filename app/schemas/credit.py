from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreditResponse(BaseModel):
    """Schema for credit response."""

    id: str
    userId: str
    type: str
    credits: int
    expiresAt: datetime | None = None
    status: str
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class CreditBalance(BaseModel):
    """Schema for credit balance response."""

    totalAvailableCredits: int
    creditsByType: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Credits grouped by type (ON_DEMAND, PERIODIC)",
    )


class CreditTransactionResponse(BaseModel):
    """Schema for credit transaction response."""

    id: str
    userId: str
    creditsId: str
    txnType: str
    creditsUsed: int
    service: str | None = None
    createdAt: datetime

    class Config:
        from_attributes = True
