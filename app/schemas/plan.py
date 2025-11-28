from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PlanCreate(BaseModel):
    """Schema for creating a plan."""

    name: str = Field(..., min_length=1, max_length=200)
    price: int = Field(..., gt=0, description="Price in paise")
    credits: int = Field(..., gt=0)
    durationInDays: int = Field(..., gt=0)
    isPrepaid: bool = Field(default=False)
    isActive: bool = Field(default=True)
    discount: int = Field(default=0, ge=0, description="Discount in paise")


class PlanUpdate(BaseModel):
    """Schema for updating a plan."""

    name: str | None = Field(None, min_length=1, max_length=200)
    price: int | None = Field(None, gt=0, description="Price in paise")
    credits: int | None = Field(None, gt=0)
    durationInDays: int | None = Field(None, gt=0)
    isPrepaid: bool | None = None
    isActive: bool | None = None
    discount: int | None = Field(None, ge=0, description="Discount in paise")
    cashfreePlanId: str | None = None


class PlanResponse(BaseModel):
    """Schema for plan response."""

    id: str
    name: str
    cashfreePlanId: str | None = None
    price: int
    credits: int
    durationInDays: int
    isPrepaid: bool
    isActive: bool
    discount: int
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True
