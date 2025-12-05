"""Organization schemas for requests and responses."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class OrganizationCreateRequest(BaseModel):
    """Request schema for organization creation."""

    name: str = Field(
        ..., min_length=1, max_length=200, description="Organization name"
    )
    orgAdminId: str = Field(..., description="Organization admin user ID")


class OrganizationUpdateRequest(BaseModel):
    """Request schema for organization updates."""

    name: str | None = Field(
        None, min_length=1, max_length=200, description="Organization name"
    )


class OrganizationResponse(BaseModel):
    """Response schema for organization data."""

    id: str
    name: str
    orgAdminId: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AddUserToOrgRequest(BaseModel):
    """Request schema for adding user to organization."""

    userId: str = Field(..., description="User ID to add to organization")
    organizationId: str = Field(..., description="Organization ID")


class OrganizationListResponse(BaseModel):
    """Response schema for organization list."""

    organizations: list[OrganizationResponse]
    total: int
