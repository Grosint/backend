from __future__ import annotations

import logging

from bson import ObjectId

from app.models.credit_txn import CreditTxn
from app.utils.validators import PyObjectId

logger = logging.getLogger(__name__)


class CreditTxnService:
    """Service for credit transaction management."""

    def __init__(self, db):
        self.db = db

    async def create_transaction(
        self,
        user_id: PyObjectId,
        credits_id: PyObjectId,
        txn_type: str,
        credits_used: int,
        service: str | None = None,
    ) -> CreditTxn:
        """Create a credit transaction record."""
        try:
            transaction = CreditTxn(
                userId=user_id,
                creditsId=credits_id,
                txnType=txn_type,
                creditsUsed=credits_used,
                service=service,
            )
            await transaction.insert()

            logger.info(
                "Credit transaction created",
                extra={
                    "transaction_id": str(transaction.id),
                    "user_id": str(user_id),
                    "credits_id": str(credits_id),
                    "txn_type": txn_type,
                    "credits_used": credits_used,
                    "service": service,
                },
            )

            return transaction

        except Exception as e:
            logger.error(
                "Error creating credit transaction",
                extra={
                    "user_id": str(user_id),
                    "credits_id": str(credits_id),
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_user_transactions(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        txn_type: str | None = None,
    ) -> list[CreditTxn]:
        """Get credit transactions for a user."""
        try:
            query = CreditTxn.find(CreditTxn.userId == ObjectId(user_id))

            if txn_type:
                query = query.find(CreditTxn.txnType == txn_type)

            transactions = (
                await query.sort(-CreditTxn.createdAt).skip(skip).limit(limit).to_list()
            )

            logger.info(
                "User credit transactions retrieved",
                extra={
                    "user_id": user_id,
                    "count": len(transactions),
                    "skip": skip,
                    "limit": limit,
                },
            )

            return transactions

        except Exception as e:
            logger.error(
                "Error getting user transactions",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            raise
