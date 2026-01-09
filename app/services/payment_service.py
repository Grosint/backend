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
                "return_url": f"{origin}/api/payments/redirect/{order_id}",
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
            # Note: Signature verification is already done in the endpoint before calling this method
            # No need to verify again here to avoid duplicate verification

            # Extract order information
            # Cashfree webhook structure: data.order.order_id for payment webhooks
            order_id = webhook_data.get("data", {}).get("order", {}).get("order_id")

            if not order_id:
                # Check if this is a test webhook (has test_object in data)
                is_test_webhook = "test_object" in webhook_data.get("data", {})
                if is_test_webhook:
                    logger.info(
                        "Test webhook received (no order_id in test payload)",
                        extra={"webhook_type": webhook_data.get("type")},
                    )
                    return {
                        "success": True,
                        "message": "Test webhook received and verified",
                    }

                logger.warning("Order ID not found in webhook data")
                return {
                    "success": False,
                    "message": "Order ID not found in webhook payload",
                }

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
            # Cashfree webhook structure: order_status might be in data.order.order_status
            # OR we need to check the event type (PAYMENT_SUCCESS_WEBHOOK = success)
            # OR check data.payment.payment_status
            event_type = webhook_data.get("type", "")
            order_status = (
                webhook_data.get("data", {})
                .get("order", {})
                .get("order_status", "")
                .lower()
            )
            payment_status = (
                webhook_data.get("data", {})
                .get("payment", {})
                .get("payment_status", "")
                .lower()
            )

            # Determine if payment is successful:
            # 1. Check order_status == "paid"
            # 2. Check payment_status == "SUCCESS" or "success"
            # 3. Check event_type indicates success (PAYMENT_SUCCESS_WEBHOOK, PAYMENT_CHARGES_WEBHOOK)
            is_paid = (
                order_status == "paid"
                or payment_status in ["success", "SUCCESS"]
                or event_type in ["PAYMENT_SUCCESS_WEBHOOK", "PAYMENT_CHARGES_WEBHOOK"]
            )

            if is_paid:
                payment.status = PaymentStatus.COMPLETED

                # Extract payment method - Cashfree sends it as nested object like {'upi': {...}} or {'card': {...}}
                # We need to extract the key (payment method type) or a string value
                payment_method_raw = (
                    webhook_data.get("data", {})
                    .get("payment", {})
                    .get("payment_method")
                )

                # Handle different payment_method formats:
                # 1. If it's a string, use it directly
                # 2. If it's a dict like {'upi': {...}}, extract the key
                # 3. If it's a dict with nested structure, try to find a method field
                if isinstance(payment_method_raw, str):
                    payment.paymentMethod = payment_method_raw
                elif isinstance(payment_method_raw, dict):
                    # Extract the first key (e.g., 'upi', 'card', 'netbanking')
                    payment_method_keys = list(payment_method_raw.keys())
                    if payment_method_keys:
                        payment.paymentMethod = payment_method_keys[
                            0
                        ].upper()  # e.g., 'UPI', 'CARD'
                    else:
                        payment.paymentMethod = None
                else:
                    payment.paymentMethod = None

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
            elif order_status in [
                "failed",
                "expired",
                "cancelled",
            ] or payment_status in ["failed", "FAILED"]:
                payment.status = order_status if order_status else payment_status
            elif event_type in [
                "PAYMENT_FAILED_WEBHOOK",
                "PAYMENT_USER_DROPPED_WEBHOOK",
            ]:
                payment.status = PaymentStatus.FAILED

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
