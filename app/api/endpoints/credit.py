"""Credit API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.schemas.credit import CreditBalance, CreditTransactionResponse
from app.schemas.response import SuccessResponse
from app.services.credit_service import CreditService
from app.services.credit_transaction_service import CreditTransactionService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/balance", response_model=SuccessResponse[CreditBalance])
async def get_credit_balance(
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Get credit balance for the current user."""
    try:
        credit_service = CreditService(db)
        credits_info = await credit_service.calculate_total_credits(
            current_user.user_id
        )

        if not credits_info.get("success"):
            raise ValueError("Failed to calculate credits")

        balance = CreditBalance(
            totalAvailableCredits=credits_info.get("total_available_credits", 0),
            creditsByType=credits_info.get("credits_by_type", {}),
        )

        logger.info(
            "Credit balance retrieved",
            extra={
                "user_id": current_user.user_id,
                "total_credits": balance.totalAvailableCredits,
            },
        )

        return SuccessResponse(
            message="Credit balance retrieved successfully",
            data=balance,
        )

    except Exception as e:
        logger.error(
            "Error getting credit balance",
            extra={"user_id": current_user.user_id, "error": str(e)},
            exc_info=True,
        )
        raise


@router.get(
    "/transactions", response_model=SuccessResponse[list[CreditTransactionResponse]]
)
async def get_credit_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    txn_type: str | None = Query(
        None, description="Filter by transaction type (CREDIT/DEBIT)"
    ),
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Get credit transaction history for the current user."""
    try:
        transaction_service = CreditTransactionService(db)
        transactions = await transaction_service.get_user_transactions(
            user_id=current_user.user_id,
            skip=skip,
            limit=limit,
            txn_type=txn_type,
        )

        transaction_responses = [
            CreditTransactionResponse(
                id=str(txn.id),
                userId=str(txn.userId),
                creditsId=str(txn.creditsId),
                txnType=txn.txnType,
                creditsUsed=txn.creditsUsed,
                service=txn.service,
                createdAt=txn.createdAt,
            )
            for txn in transactions
        ]

        logger.info(
            "Credit transactions retrieved",
            extra={
                "user_id": current_user.user_id,
                "count": len(transaction_responses),
                "skip": skip,
                "limit": limit,
            },
        )

        return SuccessResponse(
            message="Credit transactions retrieved successfully",
            data=transaction_responses,
        )

    except Exception as e:
        logger.error(
            "Error getting credit transactions",
            extra={"user_id": current_user.user_id, "error": str(e)},
            exc_info=True,
        )
        raise
