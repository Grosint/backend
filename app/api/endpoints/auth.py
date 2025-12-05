"""Authentication API endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth_dependencies import (
    TokenData,
    get_authorization_header,
    get_current_user_token,
)
from app.core.database import get_database
from app.core.exceptions import UnauthorizedException
from app.schemas.auth import (
    AuthStatus,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SendOtpRequest,
    SendOtpResponse,
    TokenInfo,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.schemas.response import SuccessResponse
from app.services.auth_service import AuthService
from app.utils.email_otp import (
    delete_otp,
    generate_otp,
    send_otp_email,
    store_otp,
    verify_otp,
)
from app.utils.validators import is_gov_email

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=SuccessResponse[LoginResponse])
async def login(login_request: LoginRequest, db=Depends(get_database)):
    """
    Authenticate user and return JWT tokens.

    Args:
        login_request: Login credentials
        db: Database dependency

    Returns:
        Login response with access and refresh tokens
    """
    try:
        auth_service = AuthService(db)
        login_response = await auth_service.login(login_request)

        return SuccessResponse(message="Login successful", data=login_response)

    except UnauthorizedException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        ) from e


@router.post("/refresh", response_model=SuccessResponse[RefreshTokenResponse])
async def refresh_token(refresh_request: RefreshTokenRequest, db=Depends(get_database)):
    """
    Refresh access token using refresh token.

    Args:
        refresh_request: Refresh token request
        db: Database dependency

    Returns:
        New access token response
    """
    try:
        auth_service = AuthService(db)
        refresh_response = await auth_service.refresh_access_token(
            refresh_request.refresh_token
        )

        return SuccessResponse(
            message="Token refreshed successfully", data=refresh_response
        )

    except UnauthorizedException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        ) from e


@router.post("/logout", response_model=SuccessResponse[LogoutResponse])
async def logout(
    logout_request: LogoutRequest,
    access_token: str = Depends(get_authorization_header),
    db=Depends(get_database),
):
    """
    Logout user and invalidate tokens.

    Args:
        logout_request: Logout request (optional refresh token)
        access_token: Access token from authorization header
        db: Database dependency

    Returns:
        Logout confirmation response
    """
    try:
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required"
            )

        auth_service = AuthService(db)
        logout_response = await auth_service.logout(
            access_token=access_token, refresh_token=logout_request.refresh_token
        )

        return SuccessResponse(message="Logout successful", data=logout_response)

    except UnauthorizedException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        ) from e


@router.post("/change-password", response_model=SuccessResponse[ChangePasswordResponse])
async def change_password(
    password_request: ChangePasswordRequest,
    token_data: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """
    Change user password.

    Args:
        password_request: Password change request
        token_data: Current user token data
        db: Database dependency

    Returns:
        Password change confirmation response
    """
    try:
        auth_service = AuthService(db)
        await auth_service.change_password(
            user_id=token_data.user_id,
            current_password=password_request.current_password,
            new_password=password_request.new_password,
        )

        return SuccessResponse(
            message="Password changed successfully",
            data=ChangePasswordResponse(
                message="Password changed successfully",
                changed_at=token_data.expires_at,  # Using token expiry as proxy for change time
            ),
        )

    except UnauthorizedException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed",
        ) from e


@router.get("/me", response_model=SuccessResponse[AuthStatus])
async def get_auth_status(token_data: TokenData = Depends(get_current_user_token)):
    """
    Get current authentication status.

    Args:
        token_data: Current user token data

    Returns:
        Authentication status information
    """
    from app.schemas.auth import AuthStatus

    auth_status = AuthStatus(
        is_authenticated=True,
        user_id=token_data.user_id,
        email=token_data.email,
        token_type=token_data.token_type,
        expires_at=token_data.expires_at,
    )

    return SuccessResponse(message="Authentication status retrieved", data=auth_status)


@router.get("/token-info", response_model=SuccessResponse[TokenInfo])
async def get_token_info(
    token_data: TokenData = Depends(get_current_user_token),
    access_token: str = Depends(get_authorization_header),
):
    """
    Get detailed token information.

    Args:
        token_data: Current user token data
        access_token: Access token from authorization header

    Returns:
        Token information
    """
    from app.schemas.auth import TokenInfo

    # Get token info from the actual token
    from app.utils.jwt import verify_access_token

    payload = verify_access_token(access_token)

    token_info = TokenInfo(
        token_type=token_data.token_type,
        user_id=token_data.user_id,
        email=token_data.email,
        issued_at=datetime.fromtimestamp(payload.get("iat", 0)),
        expires_at=token_data.expires_at,
        is_expired=False,  # If we got here, token is valid
    )

    return SuccessResponse(message="Token information retrieved", data=token_info)


@router.post("/validate", response_model=SuccessResponse[dict])
async def validate_token(
    access_token: str = Depends(get_authorization_header), db=Depends(get_database)
):
    """
    Validate token and return user information.

    Args:
        access_token: Access token to validate
        db: Database dependency

    Returns:
        Token validation result
    """
    try:
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required"
            )

        auth_service = AuthService(db)
        user = await auth_service.get_user_by_token(access_token)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

        return SuccessResponse(
            message="Token is valid",
            data={
                "valid": True,
                "user_id": str(user.id),
                "email": user.email,
                "is_active": user.isActive,
                "is_verified": user.isVerified,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token validation failed",
        ) from e


@router.post("/send-otp", response_model=SuccessResponse[SendOtpResponse])
async def send_otp(otp_request: SendOtpRequest, db=Depends(get_database)):
    """
    Send OTP to user email for verification.

    Args:
        otp_request: OTP request with email
        db: Database dependency

    Returns:
        OTP sent confirmation
    """
    try:
        from app.models.user import User

        # Check if user exists
        user = await User.find_one(User.email == otp_request.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Generate and store OTP
        otp = generate_otp()
        await store_otp(db, otp_request.email, otp)
        await send_otp_email(otp_request.email, otp)

        return SuccessResponse(
            message="OTP sent successfully to your email",
            data=SendOtpResponse(
                message="OTP sent successfully",
                expires_in=600,  # 10 minutes
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        ) from e


@router.post("/verify-otp", response_model=SuccessResponse[VerifyOtpResponse])
async def verify_otp_endpoint(
    verify_request: VerifyOtpRequest, db=Depends(get_database)
):
    """
    Verify OTP and activate user account.

    Args:
        verify_request: OTP verification request
        db: Database dependency

    Returns:
        OTP verification confirmation
    """
    try:
        from app.models.user import User

        # Normalize email to lowercase for consistent comparison
        email = verify_request.email.lower().strip()
        otp = verify_request.otp.strip()

        # Verify OTP
        is_valid = await verify_otp(db, email, otp)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP",
            )

        # Get user (use normalized email)
        user = await User.find_one(User.email == email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Update user verification status
        # If email is a gov email, set isVerified to True
        # If email is not a gov email, keep isVerified as False (admin must verify)
        if is_gov_email(user.email):
            user.isVerified = True
            await user.save()

            # Delete OTP after successful verification
            await delete_otp(db, email)

            # Send account verified email
            try:
                from app.services.email_service import email_service

                await email_service.send_account_verified_email(
                    email=user.email,
                    first_name=user.firstName,
                )
            except Exception as e:
                logger.warning(f"Failed to send account verified email: {e}")

            return SuccessResponse(
                message="OTP verified successfully. Your account is now active.",
                data=VerifyOtpResponse(
                    message="OTP verified successfully",
                    verified_at=datetime.now(),
                    is_verified=True,
                ),
            )
        else:
            # For non-gov ID users, OTP verification doesn't activate account
            # Admin must verify manually
            await delete_otp(db, email)

            return SuccessResponse(
                message="OTP verified successfully. Your account will be activated by admin.",
                data=VerifyOtpResponse(
                    message="OTP verified. Waiting for admin approval.",
                    verified_at=datetime.now(),
                    is_verified=False,
                ),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OTP verification failed",
        ) from e


@router.post("/resend-otp", response_model=SuccessResponse[SendOtpResponse])
async def resend_otp(otp_request: SendOtpRequest, db=Depends(get_database)):
    """
    Resend OTP to user email.

    Args:
        otp_request: OTP request with email
        db: Database dependency

    Returns:
        OTP sent confirmation
    """
    try:
        from app.models.user import User

        # Check if user exists
        user = await User.find_one(User.email == otp_request.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Generate and store new OTP
        otp = generate_otp()
        await store_otp(db, otp_request.email, otp)
        await send_otp_email(otp_request.email, otp)

        return SuccessResponse(
            message="OTP resent successfully to your email",
            data=SendOtpResponse(
                message="OTP resent successfully",
                expires_in=600,  # 10 minutes
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend OTP",
        ) from e
