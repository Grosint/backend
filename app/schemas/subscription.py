from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SubscriptionCreate(BaseModel):
    """Schema for creating a subscription."""

    planId: str = Field(..., description="Plan ID")
    origin: str = Field(..., description="Origin URL for redirect")


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""

    id: str
    userId: str
    planId: str
    cfSubscriptionId: str | None = None
    status: str
    startDate: datetime | None = None
    nextBillingDate: datetime | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class SubscriptionCreateResponse(BaseModel):
    """Schema for subscription creation response."""

    cashfreeSubscriptionId: str
    subscriptionSessionId: str
    redirectUrl: str | None = None
