"""
Schemas for admin debug endpoints
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PhoneLookupDebugRequest(BaseModel):
    """Request model for phone lookup debug endpoint"""

    country_code: str = Field(..., description="Country code (e.g., '+1', '+91')")
    phone: str = Field(..., description="Phone number without country code")
    include_raw_response: bool = Field(False, description="Include raw API response")


class EmailLookupDebugRequest(BaseModel):
    """Request model for email lookup debug endpoint"""

    email: str = Field(..., description="Email address to search for")
    include_raw_response: bool = Field(False, description="Include raw API response")


class SkypeSearchRequest(BaseModel):
    """Request model for Skype search endpoint"""

    email: str = Field(..., description="Email address to search for")
    include_raw_response: bool = Field(False, description="Include raw API response")


class ServiceTestResponse(BaseModel):
    """Response model for individual service test"""

    service_name: str
    success: bool
    execution_time_ms: float
    found: bool | None = None
    data: dict[str, Any] | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None
