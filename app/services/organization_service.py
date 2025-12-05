"""Organization service for managing organizations and their relationships with users."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from bson import ObjectId

from app.core.exceptions import ConflictException, NotFoundException
from app.models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationInDB,
    OrganizationUpdate,
)
from app.models.user import User, UserType

logger = logging.getLogger(__name__)


class OrganizationService:
    """Service for organization operations."""

    def __init__(self, db):
        """Initialize organization service with database connection."""
        self.db = db

    async def create_organization(
        self, org_create: OrganizationCreate
    ) -> OrganizationInDB:
        """
        Create a new organization.

        Args:
            org_create: Organization creation data

        Returns:
            Created organization

        Raises:
            ConflictException: If organization already exists for this admin
            NotFoundException: If org_admin user not found
        """
        try:
            # Check if org_admin exists and is of correct type
            org_admin = await User.find_one(User.id == ObjectId(org_create.orgAdminId))
            if not org_admin:
                raise NotFoundException(
                    resource="User", resource_id=str(org_create.orgAdminId)
                )

            if org_admin.userType != UserType.ORG_ADMIN:
                raise ConflictException(
                    message="User is not an organization admin",
                    details={"user_id": str(org_create.orgAdminId)},
                )

            # Check if organization already exists for this admin
            existing_org = await Organization.find_one(
                Organization.orgAdminId == ObjectId(org_create.orgAdminId)
            )
            if existing_org:
                raise ConflictException(
                    message="Organization already exists for this admin",
                    details={"org_admin_id": str(org_create.orgAdminId)},
                )

            # Create new organization
            new_org = Organization(
                name=org_create.name,
                orgAdminId=ObjectId(org_create.orgAdminId),
            )
            await new_org.insert()

            # Update org_admin user with orgName
            org_admin.orgName = org_create.name
            await org_admin.save()

            logger.info(
                f"Organization created: {org_create.name} by admin {org_create.orgAdminId}"
            )

            return OrganizationInDB(
                id=new_org.id,
                name=new_org.name,
                orgAdminId=new_org.orgAdminId,
                createdAt=new_org.createdAt,
                updatedAt=new_org.updatedAt,
            )

        except (ConflictException, NotFoundException):
            raise
        except Exception as e:
            logger.error(f"Error creating organization: {e}")
            raise

    async def get_organization_by_id(self, org_id: str) -> OrganizationInDB | None:
        """
        Get organization by ID.

        Args:
            org_id: Organization ID

        Returns:
            Organization or None if not found
        """
        try:
            org = await Organization.find_one(Organization.id == ObjectId(org_id))
            if org:
                return OrganizationInDB(
                    id=org.id,
                    name=org.name,
                    orgAdminId=org.orgAdminId,
                    createdAt=org.createdAt,
                    updatedAt=org.updatedAt,
                )
            return None

        except Exception as e:
            logger.error(f"Error getting organization by ID: {e}")
            raise

    async def get_organization_by_admin(
        self, org_admin_id: str
    ) -> OrganizationInDB | None:
        """
        Get organization by org admin ID.

        Args:
            org_admin_id: Organization admin user ID

        Returns:
            Organization or None if not found
        """
        try:
            org = await Organization.find_one(
                Organization.orgAdminId == ObjectId(org_admin_id)
            )
            if org:
                return OrganizationInDB(
                    id=org.id,
                    name=org.name,
                    orgAdminId=org.orgAdminId,
                    createdAt=org.createdAt,
                    updatedAt=org.updatedAt,
                )
            return None

        except Exception as e:
            logger.error(f"Error getting organization by admin: {e}")
            raise

    async def update_organization(
        self, org_id: str, org_update: OrganizationUpdate
    ) -> OrganizationInDB | None:
        """
        Update organization.

        Args:
            org_id: Organization ID
            org_update: Organization update data

        Returns:
            Updated organization or None if not found
        """
        try:
            org = await Organization.find_one(Organization.id == ObjectId(org_id))
            if not org:
                return None

            update_data = org_update.model_dump(exclude_unset=True)
            if not update_data:
                return await self.get_organization_by_id(org_id)

            # Update organization fields
            for field, value in update_data.items():
                if hasattr(org, field):
                    setattr(org, field, value)

            org.updatedAt = datetime.now(UTC)
            await org.save()

            # Update org_admin user's orgName if name changed
            if "name" in update_data:
                org_admin = await User.find_one(User.id == org.orgAdminId)
                if org_admin:
                    org_admin.orgName = update_data["name"]
                    await org_admin.save()

            return await self.get_organization_by_id(org_id)

        except Exception as e:
            logger.error(f"Error updating organization: {e}")
            raise

    async def add_user_to_organization(self, user_id: str, org_id: str) -> bool:
        """
        Add user to organization.

        Args:
            user_id: User ID to add
            org_id: Organization ID

        Returns:
            True if user added successfully

        Raises:
            NotFoundException: If user or organization not found
            ConflictException: If user is not org_user type
        """
        try:
            # Check if organization exists
            org = await Organization.find_one(Organization.id == ObjectId(org_id))
            if not org:
                raise NotFoundException(resource="Organization", resource_id=org_id)

            # Check if user exists
            user = await User.find_one(User.id == ObjectId(user_id))
            if not user:
                raise NotFoundException(resource="User", resource_id=user_id)

            # Check if user is org_user type
            if user.userType != UserType.ORG_USER:
                raise ConflictException(
                    message="User must be of type org_user to be added to organization",
                    details={"user_id": user_id, "user_type": user.userType.value},
                )

            # Update user's organizationId
            user.organizationId = ObjectId(org_id)
            await user.save()

            logger.info(f"User {user_id} added to organization {org_id}")

            return True

        except (NotFoundException, ConflictException):
            raise
        except Exception as e:
            logger.error(f"Error adding user to organization: {e}")
            raise

    async def get_org_users(self, org_id: str) -> list[User]:
        """
        Get all users in organization.

        Args:
            org_id: Organization ID

        Returns:
            List of users in organization
        """
        try:
            users = await User.find(User.organizationId == ObjectId(org_id)).to_list()

            return users

        except Exception as e:
            logger.error(f"Error getting org users: {e}")
            raise

    async def list_organizations(
        self, skip: int = 0, limit: int = 100
    ) -> list[OrganizationInDB]:
        """
        List organizations with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of organizations
        """
        try:
            cursor = Organization.find()
            orgs_docs = await cursor.skip(skip).limit(limit).to_list()
            orgs: list[OrganizationInDB] = []
            for org in orgs_docs:
                orgs.append(
                    OrganizationInDB(
                        id=org.id,
                        name=org.name,
                        orgAdminId=org.orgAdminId,
                        createdAt=org.createdAt,
                        updatedAt=org.updatedAt,
                    )
                )
            return orgs

        except Exception as e:
            logger.error(f"Error listing organizations: {e}")
            raise

    async def count_organizations(self) -> int:
        """
        Count total number of organizations.

        Returns:
            Total number of organizations
        """
        try:
            return await Organization.count()

        except Exception as e:
            logger.error(f"Error counting organizations: {e}")
            raise
