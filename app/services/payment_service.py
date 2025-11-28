from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId

from app.core.exceptions import NotFoundException
from app.models.credit import CreditType
from app.models.payment import Payment, PaymentStatus
from app.models.plan import Plan
from app.models.user import User
from app.services.credit_service import CreditService
from app.services.integrations.payment.cashfree_service import CashfreeService

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for payment management."""

    def __init__(self, db):
        self.db = db
        self.cashfree_service = CashfreeService()
        self.credit_service = CreditService(db)

    async def create_payment(
        self, user_id: str, plan_id: str, origin: str
    ) -> dict[str, Any]:
        """Create a payment order."""
        try:
            # Get user and plan
            user = await User.find_one(User.id == ObjectId(user_id))
            if not user:
                raise NotFoundException(resource="User", resource_id=user_id)

            plan = await Plan.find_one(Plan.id == ObjectId(plan_id))
            if not plan:
                raise NotFoundException(resource="Plan", resource_id=plan_id)

            if not plan.isActive:
                raise ValueError("Plan is not active")

            # Generate order ID
            order_id = self.cashfree_service.generate_order_id()

            # Prepare customer details
            customer_name = f"{user.firstName or ''} {user.lastName or ''}".strip()
            if not customer_name:
                customer_name = user.email

            customer_details = {
                "customer_name": customer_name,
                "customer_id": str(user.id),
                "customer_email": user.email,
                "customer_phone": user.phone,
            }

            # Prepare order meta and tags
            order_meta = {
                "return_url": f"{origin}/api/v1/payments/redirect/{order_id}",
            }

            order_tags = {
                "plan_id": str(plan.id),
                "order_value": str(plan.credits),
                "plan_name": plan.name,
            }

            # Create payment order in Cashfree
            cashfree_response = await self.cashfree_service.create_payment_order(
                order_id=order_id,
                amount=plan.price / 100.0,  # Convert paise to rupees
                customer_details=customer_details,
                order_meta=order_meta,
                order_tags=order_tags,
                order_note=f"Payment for {plan.name} plan",
            )

            payment_session_id = cashfree_response.get("payment_session_id")
            cf_payment_id = cashfree_response.get("cf_payment_id", "")

            if not payment_session_id:
                raise ValueError("Payment session ID not found in Cashfree response")

            # Create payment record in database
            payment = Payment(
                userId=ObjectId(user_id),
                planId=ObjectId(plan_id),
                subscriptionId=None,
                cfOrderId=order_id,
                cfPaymentId=cf_payment_id or order_id,
                amount=plan.price / 100.0,
                status=PaymentStatus.PENDING,
            )
            await payment.insert()

            logger.info(
                "Payment order created",
                extra={
                    "payment_id": str(payment.id),
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "order_id": order_id,
                    "amount": payment.amount,
                },
            )

            return {
                "paymentSessionId": payment_session_id,
                "orderId": order_id,
                "redirectUrl": cashfree_response.get("payment_session_id"),
            }

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                "Error creating payment",
                extra={"user_id": user_id, "plan_id": plan_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def verify_payment(self, order_id: str) -> dict[str, Any]:
        """Verify payment status from Cashfree."""
        try:
            # Get payment from database
            payment = await Payment.find_one(Payment.cfOrderId == order_id)
            if not payment:
                raise NotFoundException(resource="Payment", resource_id=order_id)

            # Get order details from Cashfree
            order_details = await self.cashfree_service.get_order_details(order_id)
            if not order_details:
                raise ValueError("Failed to fetch order details from Cashfree")

            # Update payment status
            order_status = order_details.get("order_status", "").lower()
            if order_status == "paid":
                payment.status = PaymentStatus.COMPLETED
                if order_details.get("payment_completion_time"):
                    payment.transactionTime = datetime.fromisoformat(
                        order_details["payment_completion_time"].replace("Z", "+00:00")
                    )
                payment.paymentMethod = order_details.get("payment_method")
            elif order_status in ["failed", "expired", "cancelled"]:
                payment.status = order_status
            else:
                payment.status = PaymentStatus.PENDING

            payment.updatedAt = datetime.now(UTC)
            await payment.save()

            # Activate credits if payment is completed
            if payment.status == PaymentStatus.COMPLETED:
                await self._activate_credits_for_payment(payment)

            logger.info(
                "Payment verified",
                extra={
                    "payment_id": str(payment.id),
                    "order_id": order_id,
                    "status": payment.status,
                },
            )

            return {
                "orderId": order_id,
                "status": payment.status,
                "amount": payment.amount,
                "paymentMethod": payment.paymentMethod,
                "transactionTime": payment.transactionTime,
            }

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                "Error verifying payment",
                extra={"order_id": order_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def process_webhook(
        self,
        webhook_data: dict[str, Any],
        raw_body: str | None = None,
        signature: str | None = None,
    ) -> dict[str, Any]:
        """Process Cashfree webhook."""
        try:
            # Verify webhook signature if provided
            if (
                signature
                and raw_body
                and not self.cashfree_service.verify_webhook_signature(
                    raw_body, signature
                )
            ):
                logger.warning("Webhook signature verification failed")
                return {"success": False, "message": "Invalid signature"}

            # Extract order information
            order_id = webhook_data.get("data", {}).get("order", {}).get("order_id")
            if not order_id:
                logger.warning("Order ID not found in webhook data")
                return {"success": False, "message": "Order ID not found"}

            # Get payment from database
            payment = await Payment.find_one(Payment.cfOrderId == order_id)
            if not payment:
                logger.warning(
                    "Payment not found for webhook", extra={"order_id": order_id}
                )
                return {"success": False, "message": "Payment not found"}

            # Check if already processed (idempotency)
            if payment.status == PaymentStatus.COMPLETED:
                logger.info(
                    "Payment already processed",
                    extra={"payment_id": str(payment.id), "order_id": order_id},
                )
                return {"success": True, "message": "Already processed"}

            # Update payment status
            order_status = (
                webhook_data.get("data", {})
                .get("order", {})
                .get("order_status", "")
                .lower()
            )
            if order_status == "paid":
                payment.status = PaymentStatus.COMPLETED
                payment.paymentMethod = (
                    webhook_data.get("data", {})
                    .get("payment", {})
                    .get("payment_method")
                )
                if (
                    webhook_data.get("data", {})
                    .get("order", {})
                    .get("payment_completion_time")
                ):
                    payment.transactionTime = datetime.fromisoformat(
                        webhook_data["data"]["order"][
                            "payment_completion_time"
                        ].replace("Z", "+00:00")
                    )
            elif order_status in ["failed", "expired", "cancelled"]:
                payment.status = order_status

            payment.updatedAt = datetime.now(UTC)
            await payment.save()

            # Activate credits if payment is completed
            if payment.status == PaymentStatus.COMPLETED:
                await self._activate_credits_for_payment(payment)

            logger.info(
                "Webhook processed",
                extra={
                    "payment_id": str(payment.id),
                    "order_id": order_id,
                    "status": payment.status,
                },
            )

            return {"success": True, "message": "Webhook processed"}

        except Exception as e:
            logger.error(
                "Error processing webhook",
                extra={"webhook_data": webhook_data, "error": str(e)},
                exc_info=True,
            )
            return {"success": False, "message": str(e)}

    async def _activate_credits_for_payment(self, payment: Payment) -> None:
        """Activate credits for a completed payment."""
        try:
            # Get plan from payment record
            if not payment.planId:
                logger.warning(
                    "Plan ID not found in payment record",
                    extra={"payment_id": str(payment.id)},
                )
                return

            plan = await Plan.find_one(Plan.id == payment.planId)
            if not plan:
                logger.warning(
                    "Plan not found",
                    extra={
                        "payment_id": str(payment.id),
                        "plan_id": str(payment.planId),
                    },
                )
                return

            # Calculate expiry date
            expires_at = None
            if plan.durationInDays > 0:
                expires_at = datetime.now(UTC) + timedelta(days=plan.durationInDays)

            # Create credit record
            await self.credit_service.create_credit(
                user_id=payment.userId,
                credit_type=CreditType.ON_DEMAND,
                credits=plan.credits,
                expires_at=expires_at,
            )

            logger.info(
                "Credits activated for payment",
                extra={
                    "payment_id": str(payment.id),
                    "user_id": str(payment.userId),
                    "credits": plan.credits,
                },
            )

        except Exception as e:
            logger.error(
                "Error activating credits for payment",
                extra={"payment_id": str(payment.id), "error": str(e)},
                exc_info=True,
            )
