from __future__ import annotations

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.search import SearchType


class SearchCreateRequest(BaseModel):
    """Request schema for creating and executing a search"""

    query: str = Field(..., description="Email, domain, or phone to search")
    search_type: SearchType = Field(
        ..., description="Type of search: email, domain, phone, or username"
    )
    user_id: PydanticObjectId | None = Field(None, description="User ID (optional)")


class PhoneLookupRequest(BaseModel):
    """Request schema for creating and executing a phone lookup search"""

    phone: str = Field(..., description="Phone number to search (without country code)")
    country_code: str = Field("+1", description="Country code (e.g., +1, +91)")
    user_id: PydanticObjectId | None = Field(None, description="User ID (optional)")
