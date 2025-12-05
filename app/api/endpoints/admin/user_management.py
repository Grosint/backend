"""Admin endpoints for user management."""

import logging

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.core.auth_dependencies import require_admin
from app.core.database import get_database
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.response import PaginatedResponse, SuccessResponse
from app.schemas.user import UserResponse
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/users/{user_id}/verify", response_model=SuccessResponse[UserResponse])
async def verify_user(
    user_id: str,
    admin_user: User = Depends(require_admin),
    db=Depends(get_database),
):
    """
    Admin verifies a non-gov ID user account.

    Args:
        user_id: User ID to verify
        admin_user: Current admin user
        db: Database dependency

    Returns:
        Updated user response
    """
    try:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
            )

        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)

        if not user:
            raise NotFoundException(resource="User", resource_id=user_id)

        # Update user verification status
        user_doc = await User.find_one(User.id == ObjectId(user_id))
        if not user_doc:
            raise NotFoundException(resource="User", resource_id=user_id)

        user_doc.isVerified = True
        await user_doc.save()

        logger.info(f"User {user_id} verified by admin {admin_user.id}")

        # Get updated user
        updated_user = await user_service.get_user_by_id(user_id)

        user_response = UserResponse(
            id=str(updated_user.id),
            email=updated_user.email,
            phone=updated_user.phone,
            userType=updated_user.userType,
            features=updated_user.features,
            firstName=updated_user.firstName,
            lastName=updated_user.lastName,
            address=updated_user.address,
            city=updated_user.city,
            pinCode=updated_user.pinCode,
            state=updated_user.state,
            organizationId=(
                str(updated_user.organizationId)
                if updated_user.organizationId
                else None
            ),
            orgName=updated_user.orgName,
            isActive=updated_user.isActive,
            isVerified=updated_user.isVerified,
            createdAt=updated_user.createdAt,
            updatedAt=updated_user.updatedAt,
        )

        return SuccessResponse(
            message="User verified successfully",
            data=user_response,
        )

    except (HTTPException, NotFoundException):
        raise
    except Exception as e:
        logger.error(f"Error verifying user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify user",
        ) from e


@router.post("/users/{user_id}/activate", response_model=SuccessResponse[UserResponse])
async def activate_user(
    user_id: str,
    is_active: bool = Query(True, description="Activate (true) or deactivate (false)"),
    admin_user: User = Depends(require_admin),
    db=Depends(get_database),
):
    """
    Admin activates or deactivates a user account.

    Args:
        user_id: User ID to activate/deactivate
        is_active: Whether to activate (true) or deactivate (false)
        admin_user: Current admin user
        db: Database dependency

    Returns:
        Updated user response
    """
    try:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
            )

        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)

        if not user:
            raise NotFoundException(resource="User", resource_id=user_id)

        # Update user active status
        user_doc = await User.find_one(User.id == ObjectId(user_id))
        if not user_doc:
            raise NotFoundException(resource="User", resource_id=user_id)

        user_doc.isActive = is_active
        await user_doc.save()

        action = "activated" if is_active else "deactivated"
        logger.info(f"User {user_id} {action} by admin {admin_user.id}")

        # Get updated user
        updated_user = await user_service.get_user_by_id(user_id)

        user_response = UserResponse(
            id=str(updated_user.id),
            email=updated_user.email,
            phone=updated_user.phone,
            userType=updated_user.userType,
            features=updated_user.features,
            firstName=updated_user.firstName,
            lastName=updated_user.lastName,
            address=updated_user.address,
            city=updated_user.city,
            pinCode=updated_user.pinCode,
            state=updated_user.state,
            organizationId=(
                str(updated_user.organizationId)
                if updated_user.organizationId
                else None
            ),
            orgName=updated_user.orgName,
            isActive=updated_user.isActive,
            isVerified=updated_user.isVerified,
            createdAt=updated_user.createdAt,
            updatedAt=updated_user.updatedAt,
        )

        return SuccessResponse(
            message=f"User {action} successfully",
            data=user_response,
        )

    except (HTTPException, NotFoundException):
        raise
    except Exception as e:
        logger.error(f"Error activating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user",
        ) from e


@router.post("/users/{user_id}/features", response_model=SuccessResponse[UserResponse])
async def assign_features(
    user_id: str,
    features: list[str] = Body(...),
    admin_user: User = Depends(require_admin),
    db=Depends(get_database),
):
    """
    Admin assigns features to a user.

    Args:
        user_id: User ID to assign features to
        features: List of feature names to assign
        admin_user: Current admin user
        db: Database dependency

    Returns:
        Updated user response
    """
    try:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
            )

        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)

        if not user:
            raise NotFoundException(resource="User", resource_id=user_id)

        # Update user features
        user_doc = await User.find_one(User.id == ObjectId(user_id))
        if not user_doc:
            raise NotFoundException(resource="User", resource_id=user_id)

        user_doc.features = features
        await user_doc.save()

        logger.info(
            f"Features {features} assigned to user {user_id} by admin {admin_user.id}"
        )

        # Get updated user
        updated_user = await user_service.get_user_by_id(user_id)

        user_response = UserResponse(
            id=str(updated_user.id),
            email=updated_user.email,
            phone=updated_user.phone,
            userType=updated_user.userType,
            features=updated_user.features,
            firstName=updated_user.firstName,
            lastName=updated_user.lastName,
            address=updated_user.address,
            city=updated_user.city,
            pinCode=updated_user.pinCode,
            state=updated_user.state,
            organizationId=(
                str(updated_user.organizationId)
                if updated_user.organizationId
                else None
            ),
            orgName=updated_user.orgName,
            isActive=updated_user.isActive,
            isVerified=updated_user.isVerified,
            createdAt=updated_user.createdAt,
            updatedAt=updated_user.updatedAt,
        )

        return SuccessResponse(
            message="Features assigned successfully",
            data=user_response,
        )

    except (HTTPException, NotFoundException):
        raise
    except Exception as e:
        logger.error(f"Error assigning features: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign features",
        ) from e


@router.get("/users/unverified", response_model=PaginatedResponse[UserResponse])
async def list_unverified_users(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    admin_user: User = Depends(require_admin),
    db=Depends(get_database),
):
    """
    List unverified users (admin only).

    Args:
        page: Page number
        size: Page size
        admin_user: Current admin user
        db: Database dependency

    Returns:
        Paginated list of unverified users
    """
    try:
        # Calculate skip
        skip = (page - 1) * size

        # Get unverified users
        unverified_users = (
            await User.find(User.isVerified == False)  # noqa: E712
            .skip(skip)
            .limit(size)
            .to_list()
        )

        total = await User.find(User.isVerified == False).count()  # noqa: E712

        # Convert to response format
        user_responses = [
            UserResponse(
                id=str(user.id),
                email=user.email,
                phone=user.phone,
                userType=user.userType,
                features=user.features,
                firstName=user.firstName,
                lastName=user.lastName,
                address=user.address,
                city=user.city,
                pinCode=user.pinCode,
                state=user.state,
                organizationId=(
                    str(user.organizationId) if user.organizationId else None
                ),
                orgName=user.orgName,
                isActive=user.isActive,
                isVerified=user.isVerified,
                createdAt=user.createdAt,
                updatedAt=user.updatedAt,
            )
            for user in unverified_users
        ]

        from app.schemas.response import PaginationMeta

        pagination = PaginationMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size,
            has_next=page * size < total,
            has_prev=page > 1,
        )

        return PaginatedResponse(
            message="Unverified users retrieved successfully",
            data=user_responses,
            pagination=pagination,
        )

    except Exception as e:
        logger.error(f"Error listing unverified users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list unverified users",
        ) from e


@router.get("/organizations", response_model=PaginatedResponse[dict])
async def list_organizations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    admin_user: User = Depends(require_admin),
    db=Depends(get_database),
):
    """
    List all organizations (admin only).

    Args:
        page: Page number
        size: Page size
        admin_user: Current admin user
        db: Database dependency

    Returns:
        Paginated list of organizations
    """
    try:
        org_service = OrganizationService(db)

        # Calculate skip
        skip = (page - 1) * size

        # Get organizations
        organizations = await org_service.list_organizations(skip=skip, limit=size)
        total = await org_service.count_organizations()

        # Convert to response format
        org_responses = [
            {
                "id": str(org.id),
                "name": org.name,
                "orgAdminId": str(org.orgAdminId),
                "createdAt": org.createdAt.isoformat(),
                "updatedAt": org.updatedAt.isoformat(),
            }
            for org in organizations
        ]

        from app.schemas.response import PaginationMeta

        pagination = PaginationMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size,
            has_next=page * size < total,
            has_prev=page > 1,
        )

        return PaginatedResponse(
            message="Organizations retrieved successfully",
            data=org_responses,
            pagination=pagination,
        )

    except Exception as e:
        logger.error(f"Error listing organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list organizations",
        ) from e
