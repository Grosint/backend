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


class BefiscLookupRequest(BaseModel):
    """Request model for Befisc lookup debug endpoint"""

    lookup_type: str = Field(
        ...,
        description="Type of lookup: phone-lookup, vehicle-lookup, bank-lookup, pan-lookup, driving-license-lookup, voter-id-lookup",
    )
    include_raw_response: bool = Field(False, description="Include raw API response")
    # Phone lookup parameters
    country_code: str | None = Field(
        None, description="Country code (e.g., '+1', '+91') - required for phone-lookup"
    )
    phone: str | None = Field(
        None,
        description="Phone number without country code - required for phone-lookup",
    )
    name: str | None = Field(None, description="Name - optional for phone-lookup")
    # Vehicle lookup parameters
    vehicle_number: str | None = Field(
        None, description="Vehicle number - required for vehicle-lookup"
    )
    # Bank lookup parameters
    account_no: str | None = Field(
        None, description="Bank account number - required for bank-lookup"
    )
    ifsc_code: str | None = Field(
        None, description="IFSC code - required for bank-lookup"
    )
    upi: str | None = Field(None, description="UPI ID - optional for bank-lookup")
    # PAN lookup parameters
    pan: str | None = Field(None, description="PAN number - required for pan-lookup")
    # Driving license lookup parameters
    license_number: str | None = Field(
        None, description="Driving license number - required for driving-license-lookup"
    )
    dob: str | None = Field(
        None,
        description="Date of birth (DD-MM-YYYY) - required for driving-license-lookup",
    )
    # Voter ID lookup parameters
    epic_number: str | None = Field(
        None, description="EPIC number - required for voter-id-lookup"
    )


class AITANLookupRequest(BaseModel):
    """Request model for AITAN lookup debug endpoint"""

    lookup_type: str = Field(
        ...,
        description="Type of lookup: phone-lookup, vehicle-lookup, bank-lookup",
    )
    include_raw_response: bool = Field(False, description="Include raw API response")
    # Phone lookup parameters
    country_code: str | None = Field(
        None, description="Country code (e.g., '+1', '+91') - required for phone-lookup"
    )
    phone: str | None = Field(
        None,
        description="Phone number without country code - required for phone-lookup, optional for bank-lookup (phone-based)",
    )
    # Vehicle lookup parameters
    vehicle_number: str | None = Field(
        None, description="Vehicle number - required for vehicle-lookup"
    )
    chassis_number: str | None = Field(
        None, description="Chassis number - optional for vehicle-lookup"
    )
    # Bank lookup parameters
    account_no: str | None = Field(
        None, description="Bank account number - required for bank-lookup"
    )
    ifsc_code: str | None = Field(
        None, description="IFSC code - required for bank-lookup"
    )
    upi: str | None = Field(None, description="UPI ID - optional for bank-lookup")


class AITANVehicleLookupRequest(BaseModel):
    """Request model for AITAN vehicle lookup debug endpoint"""

    vehicle_number: str | None = Field(
        None, description="Vehicle registration number - required for most lookups"
    )
    chassis_number: str | None = Field(
        None, description="Chassis number - optional for chassis_to_rc lookup"
    )
    include_raw_response: bool = Field(False, description="Include raw API response")
