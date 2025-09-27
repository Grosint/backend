import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_database
from app.core.security import get_current_user
from app.models.user import UserCreate, UserUpdate
from app.schemas.auth import TokenData
from app.schemas.user import (
    UserCreateRequest,
    UserCreateResponse,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=UserCreateResponse)
async def create_user(user_request: UserCreateRequest, db=Depends(get_database)):
    """Create a new user"""
    try:
        user_service = UserService(db)

        # Create user
        user_create = UserCreate(
            email=user_request.email,
            phone=user_request.phone,
            password=user_request.password,
            verifyByGovId=user_request.verifyByGovId,
        )

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

        return UserCreateResponse(
            message="User created successfully",
            user_id=str(user.id),
            user=user_response,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        ) from e


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_user), db=Depends(get_database)
):
    """Get current user information"""
    try:
        user_service = UserService(db)

        # Get user by username (from token)
        user = await user_service.get_user_by_username(current_user.username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            createdAt=user.createdAt,
            updatedAt=user.updatedAt,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information",
        ) from e


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdateRequest,
    current_user: TokenData = Depends(get_current_user),
    db=Depends(get_database),
):
    """Update current user information"""
    try:
        user_service = UserService(db)

        # Get current user
        user = await user_service.get_user_by_username(current_user.username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Update user
        update_data = UserUpdate(**user_update.dict(exclude_unset=True))
        updated_user = await user_service.update_user(str(user.id), update_data)

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserResponse(
            id=str(updated_user.id),
            email=updated_user.email,
            username=updated_user.username,
            full_name=updated_user.full_name,
            is_active=updated_user.is_active,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        ) from e


@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    db=Depends(get_database),
):
    """List users with pagination (admin only)"""
    try:
        user_service = UserService(db)

        # Calculate skip
        skip = (page - 1) * size

        # Get users
        users = await user_service.list_users(skip=skip, limit=size)

        # Convert to response format
        user_responses = [
            UserResponse(
                id=str(user.id),
                email=user.email,
                username=user.username,
                full_name=user.full_name,
                is_active=user.is_active,
                createdAt=user.createdAt,
                updatedAt=user.updatedAt,
            )
            for user in users
        ]

        return UserListResponse(
            users=user_responses, total=len(user_responses), page=page, size=size
        )

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users",
        ) from e


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: TokenData = Depends(get_current_user),
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        logger.info(f"User deleted: {user_id}")

        return {"message": "User deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        ) from e
