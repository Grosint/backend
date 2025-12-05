"""Organization model for managing organizations and their relationships with users."""

from __future__ import annotations

from datetime import UTC, datetime

from beanie import Document, Indexed, Insert, Replace, before_event
from bson import ObjectId
from pydantic import BaseModel, Field

from app.utils.validators import PyObjectId


class OrganizationBase(BaseModel):
    """Base organization model."""

    name: str = Field(..., description="Organization name")
    orgAdminId: PyObjectId = Field(..., description="Organization admin user ID")
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrganizationCreate(BaseModel):
    """Model for organization creation."""

    name: str = Field(..., description="Organization name")
    orgAdminId: PyObjectId = Field(..., description="Organization admin user ID")


class OrganizationUpdate(BaseModel):
    """Model for organization updates."""

    name: str | None = None


class OrganizationInDB(OrganizationBase):
    """Organization model for database operations."""

    id: PyObjectId = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Organization(Document):
    """Organization document model."""

    name: Indexed(str, unique=False)
    orgAdminId: Indexed(PyObjectId, unique=True)  # One org_admin per organization
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @before_event([Insert, Replace])
    def set_timestamps(self):
        """Set timestamps before insert or replace."""
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    class Settings:
        name = "organizations"
        indexes = [
            [("orgAdminId", 1)],  # Index for org admin queries
            [("name", 1)],  # Index for organization name queries
        ]
