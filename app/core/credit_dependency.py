"""Credit checking dependency for FastAPI endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.core.exceptions import BusinessLogicException
from app.services.credit_service import CreditService

logger = logging.getLogger(__name__)


def credits_required(credit_amount: int = 1):
    """
    Dependency factory to check and deduct credits before endpoint execution.

    Args:
        credit_amount: Number of credits required for the operation

    Returns:
        FastAPI dependency function
    """

    async def check_credits(
        token_data: TokenData = Depends(get_current_user_token),
        db=Depends(get_database),
    ) -> dict[str, Any]:
        """
        Check and deduct credits for the current user.

        Args:
            token_data: Current user token data
            db: Database instance

        Returns:
            Dictionary with credit deduction result

        Raises:
            HTTPException: If insufficient credits
        """
        try:
            credit_service = CreditService(db)

            # Calculate available credits
            credits_info = await credit_service.calculate_total_credits(
                token_data.user_id
            )
            total_available = credits_info.get("total_available_credits", 0)

            if total_available < credit_amount:
                logger.warning(
                    "Insufficient credits",
                    extra={
                        "user_id": token_data.user_id,
                        "required": credit_amount,
                        "available": total_available,
                    },
                )
                raise BusinessLogicException(
                    message="Insufficient credits",
                    error_code="INSUFFICIENT_CREDITS",
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    details={
                        "required": credit_amount,
                        "available": total_available,
                    },
                )

            # Deduct credits
            deduction_result = await credit_service.deduct_credits(
                user_id=token_data.user_id,
                credit_amount=credit_amount,
                service="API_ENDPOINT_DEDUCTION",
            )

            if not deduction_result.get("success"):
                logger.error(
                    "Failed to deduct credits",
                    extra={
                        "user_id": token_data.user_id,
                        "amount": credit_amount,
                        "result": deduction_result,
                    },
                )
                raise BusinessLogicException(
                    message="Failed to deduct credits",
                    error_code="CREDIT_DEDUCTION_FAILED",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    details=deduction_result,
                )

            logger.info(
                "Credits deducted",
                extra={
                    "user_id": token_data.user_id,
                    "amount": credit_amount,
                    "remaining": total_available - credit_amount,
                },
            )

            return deduction_result

        except BusinessLogicException:
            raise
        except Exception as e:
            logger.error(
                "Error checking credits",
                extra={
                    "user_id": token_data.user_id,
                    "amount": credit_amount,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing credit deduction",
            ) from e

    return check_credits
