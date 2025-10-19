import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.core.exceptions import NotFoundException
from app.models.user import UserCreate, UserUpdate
from app.schemas.response import PaginatedResponse, SuccessResponse
from app.schemas.user import (
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=SuccessResponse[UserResponse])
async def create_user(user_request: UserCreateRequest, db=Depends(get_database)):
    """Create a new user"""
    try:
        user_service = UserService(db)

        # Create user - convert request to service model
        user_create = UserCreate.model_validate(user_request.model_dump())

        user = await user_service.create_user(user_create)

        # Convert to response format
        user_response = UserResponse(
            id=str(user.id),
            email=user.email,
            phone=user.phone,
            firstName=user.firstName,
            lastName=user.lastName,
            pinCode=user.pinCode,
            state=user.state,
            isActive=user.isActive,
            isVerified=user.isVerified,
            verifyByGovId=user.verifyByGovId,
            createdAt=user.createdAt,
            updatedAt=user.updatedAt,
        )

        logger.info(f"User created: {user.email}")

        return SuccessResponse(
            message="User created successfully",
            data=user_response,
        )

    except Exception:
        # Let the global exception handler deal with it
        raise


@router.get("/me", response_model=SuccessResponse[UserResponse])
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_user_token), db=Depends(get_database)
):
    """Get current user information"""
    try:
        user_service = UserService(db)

        # Get user by ID (from token)
        user = await user_service.get_user_by_id(current_user.user_id)
        if not user:
            raise NotFoundException(resource="User", resource_id=current_user.user_id)

        user_response = UserResponse(
            id=str(user.id),
            email=user.email,
            phone=user.phone,
            verifyByGovId=user.verifyByGovId,
            firstName=user.firstName,
            lastName=user.lastName,
            pinCode=user.pinCode,
            state=user.state,
            isActive=user.isActive,
            isVerified=user.isVerified,
            createdAt=user.createdAt,
            updatedAt=user.updatedAt,
        )

        return SuccessResponse(
            message="User information retrieved successfully",
            data=user_response,
        )

    except Exception:
        # Let the global exception handler deal with it
        raise


@router.put("/me", response_model=SuccessResponse[UserResponse])
async def update_current_user(
    user_update: UserUpdateRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Update current user information"""
    try:
        user_service = UserService(db)

        # Get current user
        user = await user_service.get_user_by_id(current_user.user_id)
        if not user:
            raise NotFoundException(resource="User", resource_id=current_user.user_id)

        # Update user
        update_data = UserUpdate(**user_update.model_dump(exclude_unset=True))
        updated_user = await user_service.update_user(str(user.id), update_data)

        if not updated_user:
            raise NotFoundException(resource="User", resource_id=str(user.id))

        user_response = UserResponse(
            id=str(updated_user.id),
            email=updated_user.email,
            phone=updated_user.phone,
            verifyByGovId=updated_user.verifyByGovId,
            firstName=updated_user.firstName,
            lastName=updated_user.lastName,
            pinCode=updated_user.pinCode,
            state=updated_user.state,
            isActive=updated_user.isActive,
            isVerified=updated_user.isVerified,
            createdAt=updated_user.createdAt,
            updatedAt=updated_user.updatedAt,
        )

        return SuccessResponse(
            message="User updated successfully",
            data=user_response,
        )

    except Exception:
        # Let the global exception handler deal with it
        raise


@router.get("/list", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """List users with pagination (admin only)"""
    try:
        user_service = UserService(db)

        # Calculate skip
        skip = (page - 1) * size

        # Get users
        users = await user_service.list_users(skip=skip, limit=size)
        total = await user_service.count_users()

        # Convert to response format
        user_responses = [
            UserResponse(
                id=str(user.id),
                email=user.email,
                phone=user.phone,
                verifyByGovId=user.verifyByGovId,
                firstName=user.firstName,
                lastName=user.lastName,
                pinCode=user.pinCode,
                state=user.state,
                isActive=user.isActive,
                isVerified=user.isVerified,
                createdAt=user.createdAt,
                updatedAt=user.updatedAt,
            )
            for user in users
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
            message="Users retrieved successfully",
            data=user_responses,
            pagination=pagination,
        )

    except Exception:
        # Let the global exception handler deal with it
        raise


@router.delete("/{user_id}", response_model=SuccessResponse[dict])
async def delete_user(
    user_id: str,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Delete a user (admin only)"""
    try:
        user_service = UserService(db)

        # Validate user ID
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
            )

        # Delete user
        deleted = await user_service.delete_user(user_id)
        if not deleted:
            raise NotFoundException(resource="User", resource_id=user_id)

        logger.info(f"User deleted: {user_id}")

        return SuccessResponse(
            message="User deleted successfully", data={"deleted_user_id": user_id}
        )

    except HTTPException:
        raise
    except Exception:
        # Let the global exception handler deal with it
        raise
