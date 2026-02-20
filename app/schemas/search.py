from __future__ import annotations

from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.search import SearchType


class SearchCreateRequest(BaseModel):
    """Request schema for creating and executing a search"""

    query: str = Field(..., description="Email, domain, phone, or vehicle to search")
    search_type: SearchType = Field(
        ...,
        description=(
            "Type of search: email, domain, phone, "
            "vehicle-rc, vehicle-fast-tag, vehicle-all, vehicle-chasis, or username"
        ),
    )
    user_id: PydanticObjectId | None = Field(None, description="User ID (optional)")


class PhoneLookupRequest(BaseModel):
    """Request schema for creating and executing a phone lookup search"""

    phone: str = Field(..., description="Phone number to search (without country code)")
    country_code: str = Field("+1", description="Country code (e.g., +1, +91)")
    is_advance: bool = Field(
        False,
        description=(
            "Whether to enable advanced AITAN phone lookup. "
            "If true, additional AITAN sources will be queried."
        ),
    )


class VehicleLookupRequest(BaseModel):
    """Request schema for creating and executing a vehicle lookup search"""

    vehicle_number: str | None = Field(
        None,
        description="Vehicle registration number to search",
    )
    chassis_number: str | None = Field(
        None,
        description="Chassis number (optional, used for chassis-to-RC lookup)",
    )
    lookup_type: Literal["rc", "fast-tag", "chasis", "chassis", "all"] = Field(
        "all",
        description=(
            "Which results to return: rc, fast-tag, chasis/chassis (chassis + rc), "
            "or all."
        ),
    )


class EmailLookupRequest(BaseModel):
    """Request schema for creating and executing an email lookup search"""

    email: str = Field(..., description="Email address to search")


class BankLookupRequest(BaseModel):
    """Request schema for bank account lookup (account+IFSC or UPI)"""

    account_no: str | None = Field(None, description="Bank account number")
    ifsc_code: str | None = Field(None, description="IFSC code")
    upi: str | None = Field(None, description="UPI ID (e.g. user@paytm)")


class VerifyIdRequest(BaseModel):
    """Request schema for ID verification (PAN, DL, Voter ID)"""

    id_type: Literal["pan", "dl", "voter", "passport"] = Field(
        ..., description="Type of ID to verify"
    )
    value: str = Field(..., description="ID value (PAN, license number, epic number)")
    dob: str | None = Field(
        None,
        description="Date of birth DD-MM-YYYY (required for driving license)",
    )


class IPLookupRequest(BaseModel):
    """Request schema for IP lookup"""

    ip: str = Field(..., description="IP address to lookup")


class IMEILookupRequest(BaseModel):
    """Request schema for IMEI lookup"""

    imei: str = Field(..., description="IMEI number (15 digits)")


class VirtualNumberLookupRequest(BaseModel):
    """Request schema for virtual number check"""

    phone_number: str = Field(..., description="Phone number to check")
    country_code: str = Field(
        "+91",
        description="Country code for E.164 format (e.g. +91, +1). Used when phone_number lacks + prefix.",
    )


class VirtualEmailLookupRequest(BaseModel):
    """Request schema for virtual/disposable email check"""

    email: str = Field(..., description="Email address to check")
