"""Common profiler schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TimestampMixin(BaseModel):
    """UTC timestamp fields."""

    created_at: datetime | None = None
    updated_at: datetime | None = None
