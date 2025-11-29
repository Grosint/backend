from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    """Schema for creating a payment order."""

    planId: str = Field(..., description="Plan ID")
    origin: str = Field(..., description="Origin URL for redirect")


class PaymentResponse(BaseModel):
    """Schema for payment response."""

    id: str
    userId: str
    planId: str | None = None
    subscriptionId: str | None = None
    cfPaymentId: str
    cfOrderId: str
    amount: float
    status: str
    paymentMethod: str | None = None
    transactionTime: datetime | None = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class PaymentCreateResponse(BaseModel):
    """Schema for payment creation response."""

    paymentSessionId: str
    orderId: str
    redirectUrl: str | None = None


class PaymentVerifyResponse(BaseModel):
    """Schema for payment verification response."""

    orderId: str
    status: str
    amount: float
    paymentMethod: str | None = None
    transactionTime: datetime | None = None


class WebhookPayload(BaseModel):
    """Schema for Cashfree webhook payload."""

    type: str = Field(..., description="Webhook event type")
    data: dict[str, Any] = Field(..., description="Webhook data")
    eventTime: str | None = Field(None, description="Event timestamp")
