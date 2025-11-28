from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.models.credit import Credit, CreditStatus, CreditType
from app.models.credit_transaction import TransactionType
from app.services.credit_transaction_service import CreditTransactionService
from app.utils.validators import PyObjectId

logger = logging.getLogger(__name__)


class CreditService:
    """Service for credit management."""

    def __init__(self, db):
        self.db = db
        self.transaction_service = CreditTransactionService(db)

    async def create_credit(
        self,
        user_id: PyObjectId,
        credit_type: str,
        credits: int,
        expires_at: datetime | None = None,
    ) -> Credit:
        """Create a credit record."""
        try:
            credit = Credit(
                userId=user_id,
                type=credit_type,
                credits=credits,
                expiresAt=expires_at,
                status=CreditStatus.ACTIVE,
            )
            await credit.insert()

            # Create transaction record
            await self.transaction_service.create_transaction(
                user_id=user_id,
                credits_id=credit.id,
                txn_type=TransactionType.CREDIT,
                credits_used=credits,
                service="CREDIT_CREATED",
            )

            logger.info(
                "Credit created",
                extra={
                    "credit_id": str(credit.id),
                    "user_id": str(user_id),
                    "type": credit_type,
                    "credits": credits,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
            )

            return credit

        except Exception as e:
            logger.error(
                "Error creating credit",
                extra={
                    "user_id": str(user_id),
                    "type": credit_type,
                    "credits": credits,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def calculate_total_credits(self, user_id: str) -> dict[str, Any]:
        """Calculate total available credits for a user."""
        try:
            current_date = datetime.now(UTC)

            # Get active credits that haven't expired
            active_credits = await Credit.find(
                Credit.userId == ObjectId(user_id),
                Credit.status == CreditStatus.ACTIVE,
            ).to_list()

            # Filter credits that haven't expired
            valid_credits = [
                credit
                for credit in active_credits
                if credit.expiresAt is None or credit.expiresAt > current_date
            ]

            # Group by type
            credits_by_type: dict[str, dict[str, Any]] = {}
            total_available = 0

            for credit in valid_credits:
                credit_type = credit.type
                if credit_type not in credits_by_type:
                    credits_by_type[credit_type] = {
                        "totalCredits": 0,
                        "credits": [],
                    }

                credits_by_type[credit_type]["totalCredits"] += credit.credits
                credits_by_type[credit_type]["credits"].append(
                    {
                        "creditsId": str(credit.id),
                        "credits": credit.credits,
                        "expiresAt": (
                            credit.expiresAt.isoformat() if credit.expiresAt else None
                        ),
                        "createdAt": credit.createdAt.isoformat(),
                    }
                )
                total_available += credit.credits

            result = {
                "success": True,
                "total_available_credits": total_available,
                "credits_by_type": credits_by_type,
            }

            logger.info(
                "Total credits calculated",
                extra={
                    "user_id": user_id,
                    "total_credits": total_available,
                    "credits_by_type": credits_by_type,
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Error calculating total credits",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            return {
                "success": False,
                "total_available_credits": 0,
                "credits_by_type": {},
                "error": str(e),
            }

    async def deduct_credits(
        self, user_id: str, credit_amount: int, service: str = "SERVICE_DEDUCTION"
    ) -> dict[str, Any]:
        """Deduct credits from user account (FIFO: PERIODIC first, then ON_DEMAND)."""
        try:
            # Get available credits
            credits_info = await self.calculate_total_credits(user_id)
            if not credits_info.get("success"):
                return {"success": False, "message": "Failed to calculate credits"}

            credits_by_type = credits_info.get("credits_by_type", {})
            remaining_to_deduct = credit_amount
            transactions_created = []

            # Deduct from PERIODIC credits first (sorted by expiry)
            if CreditType.PERIODIC in credits_by_type and remaining_to_deduct > 0:
                periodic_credits = sorted(
                    credits_by_type[CreditType.PERIODIC]["credits"],
                    key=lambda x: x.get("expiresAt") or "9999-12-31",
                )

                for credit_entry in periodic_credits:
                    if remaining_to_deduct <= 0:
                        break

                    credit_obj = await Credit.find_one(
                        Credit.id == ObjectId(credit_entry["creditsId"])
                    )
                    if not credit_obj:
                        continue

                    deduct_amount = min(remaining_to_deduct, credit_obj.credits)
                    remaining_to_deduct -= deduct_amount
                    credit_obj.credits -= deduct_amount

                    if credit_obj.credits <= 0:
                        credit_obj.status = CreditStatus.EXPIRED

                    credit_obj.updatedAt = datetime.now(UTC)
                    await credit_obj.save()

                    # Create transaction record
                    await self.transaction_service.create_transaction(
                        user_id=ObjectId(user_id),
                        credits_id=credit_obj.id,
                        txn_type=TransactionType.DEBIT,
                        credits_used=deduct_amount,
                        service=service,
                    )

                    transactions_created.append(
                        {
                            "credits_id": str(credit_obj.id),
                            "deducted": deduct_amount,
                            "remaining": credit_obj.credits,
                        }
                    )

            # Deduct from ON_DEMAND credits if needed (sorted by creation date)
            if CreditType.ON_DEMAND in credits_by_type and remaining_to_deduct > 0:
                on_demand_credits = sorted(
                    credits_by_type[CreditType.ON_DEMAND]["credits"],
                    key=lambda x: x.get("createdAt", ""),
                )

                for credit_entry in on_demand_credits:
                    if remaining_to_deduct <= 0:
                        break

                    credit_obj = await Credit.find_one(
                        Credit.id == ObjectId(credit_entry["creditsId"])
                    )
                    if not credit_obj:
                        continue

                    deduct_amount = min(remaining_to_deduct, credit_obj.credits)
                    remaining_to_deduct -= deduct_amount
                    credit_obj.credits -= deduct_amount

                    if credit_obj.credits <= 0:
                        credit_obj.status = CreditStatus.EXPIRED

                    credit_obj.updatedAt = datetime.now(UTC)
                    await credit_obj.save()

                    # Create transaction record
                    await self.transaction_service.create_transaction(
                        user_id=ObjectId(user_id),
                        credits_id=credit_obj.id,
                        txn_type=TransactionType.DEBIT,
                        credits_used=deduct_amount,
                        service=service,
                    )

                    transactions_created.append(
                        {
                            "credits_id": str(credit_obj.id),
                            "deducted": deduct_amount,
                            "remaining": credit_obj.credits,
                        }
                    )

            if remaining_to_deduct > 0:
                logger.warning(
                    "Insufficient credits for deduction",
                    extra={
                        "user_id": user_id,
                        "requested": credit_amount,
                        "deducted": credit_amount - remaining_to_deduct,
                        "remaining_needed": remaining_to_deduct,
                    },
                )
                return {
                    "success": False,
                    "message": "Not enough credits to deduct the requested amount",
                    "deducted": credit_amount - remaining_to_deduct,
                    "remaining_needed": remaining_to_deduct,
                }

            logger.info(
                "Credits deducted successfully",
                extra={
                    "user_id": user_id,
                    "amount": credit_amount,
                    "transactions": len(transactions_created),
                },
            )

            return {
                "success": True,
                "message": "Credits deducted successfully",
                "deducted": credit_amount,
                "transactions": transactions_created,
            }

        except Exception as e:
            logger.error(
                "Error deducting credits",
                extra={"user_id": user_id, "amount": credit_amount, "error": str(e)},
                exc_info=True,
            )
            return {"success": False, "message": f"Error deducting credits: {str(e)}"}

    async def expire_credits(self) -> dict[str, Any]:
        """Expire credits that have passed their expiry date."""
        try:
            current_date = datetime.now(UTC)
            expired_credits = await Credit.find(
                Credit.expiresAt < current_date,
                Credit.status == CreditStatus.ACTIVE,
            ).to_list()

            expired_count = 0
            total_expired_amount = 0

            for credit in expired_credits:
                try:
                    credit.status = CreditStatus.EXPIRED
                    credit.updatedAt = datetime.now(UTC)
                    await credit.save()

                    # Create transaction record
                    if credit.credits > 0:
                        await self.transaction_service.create_transaction(
                            user_id=credit.userId,
                            credits_id=credit.id,
                            txn_type=TransactionType.DEBIT,
                            credits_used=credit.credits,
                            service="CREDIT_EXPIRED",
                        )
                        total_expired_amount += credit.credits

                    expired_count += 1

                except Exception as e:
                    logger.error(
                        "Error processing expired credit",
                        extra={"credit_id": str(credit.id), "error": str(e)},
                        exc_info=True,
                    )
                    continue

            logger.info(
                "Credits expired",
                extra={
                    "expired_count": expired_count,
                    "total_expired_amount": total_expired_amount,
                },
            )

            return {
                "success": True,
                "expired_count": expired_count,
                "total_expired_amount": total_expired_amount,
            }

        except Exception as e:
            logger.error(
                "Error expiring credits", extra={"error": str(e)}, exc_info=True
            )
            return {"success": False, "error": str(e)}
