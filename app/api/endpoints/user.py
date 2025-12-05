import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.core.exceptions import NotFoundException
from app.models.user import UserCreate, UserUpdate
from app.schemas.response import PaginatedResponse, SuccessResponse
from app.schemas.user import UserCreateRequest, UserResponse, UserUpdateRequest
from app.services.user_service import UserService
from app.utils.email_otp import generate_otp, send_otp_email, store_otp

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=SuccessResponse[UserResponse])
async def create_user(user_request: UserCreateRequest, db=Depends(get_database)):
    """Create a new user and send OTP for verification"""
    try:
        user_service = UserService(db)

        # Convert organizationId from string to ObjectId if provided
        user_data = user_request.model_dump()
        if user_data.get("organizationId"):
            user_data["organizationId"] = ObjectId(user_data["organizationId"])

        # Create user - convert request to service model
        user_create = UserCreate.model_validate(user_data)

        user = await user_service.create_user(user_create)

        # Generate and send OTP - wrap in error handling to rollback user creation on failure
        try:
            otp = generate_otp()

            # Store OTP - check return value
            store_result = await store_otp(db, user.email, otp)
            if not store_result:
                logger.error(
                    f"Failed to store OTP for user {user.email} (ID: {user.id}). "
                    f"Rolling back user creation."
                )
                # Rollback: delete the created user
                await user_service.delete_user(str(user.id))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to store OTP. User creation rolled back. Please try again.",
                )

            # Send OTP email - check return value
            send_result = await send_otp_email(user.email, otp)
            if not send_result:
                logger.error(
                    f"Failed to send OTP email to user {user.email} (ID: {user.id}). "
                    f"Rolling back user creation."
                )
                # Rollback: delete the created user
                await user_service.delete_user(str(user.id))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send OTP email. User creation rolled back. Please try again.",
                )

            logger.info(f"User created: {user.email}, OTP sent")
        except HTTPException:
            # Re-raise HTTPExceptions (already handled above)
            raise
        except Exception as e:
            # Catch any other exceptions during OTP operations
            logger.error(
                f"Unexpected error during OTP operations for user {user.email} (ID: {user.id}): {e}",
                exc_info=True,
            )
            # Rollback: delete the created user
            try:
                await user_service.delete_user(str(user.id))
            except Exception as delete_error:
                logger.error(
                    f"Failed to rollback user creation for {user.email} (ID: {user.id}): {delete_error}"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete user registration. Please try again.",
            ) from e

        # Convert to response format
        user_response = UserResponse(
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
            organizationId=str(user.organizationId) if user.organizationId else None,
            orgName=user.orgName,
            isActive=user.isActive,
            isVerified=user.isVerified,
            createdAt=user.createdAt,
            updatedAt=user.updatedAt,
        )

        return SuccessResponse(
            message="User created successfully. Please verify your email with the OTP sent.",
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
            userType=user.userType,
            features=user.features,
            firstName=user.firstName,
            lastName=user.lastName,
            address=user.address,
            city=user.city,
            pinCode=user.pinCode,
            state=user.state,
            organizationId=str(user.organizationId) if user.organizationId else None,
            orgName=user.orgName,
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

        # Update user - convert organizationId from string to ObjectId if provided
        update_dict = user_update.model_dump(exclude_unset=True)
        if update_dict.get("organizationId"):
            update_dict["organizationId"] = ObjectId(update_dict["organizationId"])

        update_data = UserUpdate(**update_dict)
        updated_user = await user_service.update_user(str(user.id), update_data)

        if not updated_user:
            raise NotFoundException(resource="User", resource_id=str(user.id))

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

        # Convert to response format (excluding sensitive fields like userType and features)
        user_responses = [
            UserResponse(
                id=str(user.id),
                email=user.email,
                phone=user.phone,
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
