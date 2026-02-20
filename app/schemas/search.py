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
