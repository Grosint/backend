from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId

from app.core.exceptions import NotFoundException
from app.models.credit import CreditType
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.credit_service import CreditService
from app.services.integrations.payment.cashfree_service import CashfreeService

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for subscription management."""

    def __init__(self, db):
        self.db = db
        self.cashfree_service = CashfreeService()
        self.credit_service = CreditService(db)

    async def create_subscription(
        self, user_id: str, plan_id: str, origin: str
    ) -> dict[str, Any]:
        """Create a subscription."""
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

            if plan.isPrepaid:
                raise ValueError("Cannot create subscription for prepaid plan")

            if not plan.cashfreePlanId:
                raise ValueError("Plan does not have Cashfree plan ID")

            # Cancel existing subscriptions for this user
            # Query for active or pending subscriptions
            active_subs = await Subscription.find(
                Subscription.userId == ObjectId(user_id),
                Subscription.status == SubscriptionStatus.ACTIVE,
            ).to_list()
            pending_subs = await Subscription.find(
                Subscription.userId == ObjectId(user_id),
                Subscription.status == SubscriptionStatus.PENDING,
            ).to_list()
            existing_subscriptions = active_subs + pending_subs

            for existing_sub in existing_subscriptions:
                if existing_sub.cfSubscriptionId:
                    try:
                        await self.cashfree_service.cancel_subscription(
                            existing_sub.cfSubscriptionId
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to cancel existing subscription in Cashfree",
                            extra={
                                "subscription_id": str(existing_sub.id),
                                "error": str(e),
                            },
                        )

                existing_sub.status = SubscriptionStatus.CANCELLED
                existing_sub.updatedAt = datetime.now(UTC)
                await existing_sub.save()

            # Generate subscription ID
            subscription_id = self.cashfree_service.generate_subscription_id()

            # Prepare customer details
            customer_name = f"{user.firstName or ''} {user.lastName or ''}".strip()
            if not customer_name:
                customer_name = user.email

            customer_details = {
                "customer_name": customer_name,
                "customer_email": user.email,
                "customer_phone": user.phone,
            }

            # Prepare subscription meta and tags
            subscription_meta = {
                "return_url": f"{origin}/api/subscriptions/redirect/{subscription_id}",
            }

            subscription_tags = {
                "description": f"Subscription for {plan.name} plan",
            }

            # Calculate dates
            subscription_expiry_time = (
                datetime.now(UTC) + timedelta(days=5 * 365)
            ).isoformat()
            subscription_first_charge_time = (
                datetime.now(UTC) + timedelta(days=2)
            ).isoformat()

            # Create subscription in Cashfree
            cashfree_response = await self.cashfree_service.create_subscription(
                subscription_id=subscription_id,
                customer_details=customer_details,
                plan_id=plan.cashfreePlanId,
                subscription_meta=subscription_meta,
                subscription_expiry_time=subscription_expiry_time,
                subscription_first_charge_time=subscription_first_charge_time,
                subscription_tags=subscription_tags,
            )

            cf_subscription_id = cashfree_response.get("subscription_id")
            subscription_session_id = cashfree_response.get("subscription_session_id")

            if not cf_subscription_id or not subscription_session_id:
                raise ValueError(
                    "Subscription ID or session ID not found in Cashfree response"
                )

            # Create subscription record in database
            subscription = Subscription(
                userId=ObjectId(user_id),
                planId=ObjectId(plan_id),
                cfSubscriptionId=cf_subscription_id,
                status=SubscriptionStatus.INITIALIZED,
            )
            await subscription.insert()

            logger.info(
                "Subscription created",
                extra={
                    "subscription_id": str(subscription.id),
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "cf_subscription_id": cf_subscription_id,
                },
            )

            return {
                "cashfreeSubscriptionId": cf_subscription_id,
                "subscriptionSessionId": subscription_session_id,
                "redirectUrl": subscription_session_id,
            }

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                "Error creating subscription",
                extra={"user_id": user_id, "plan_id": plan_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel a subscription."""
        try:
            subscription = await Subscription.find_one(
                Subscription.id == ObjectId(subscription_id)
            )
            if not subscription:
                raise NotFoundException(
                    resource="Subscription", resource_id=subscription_id
                )

            # Cancel in Cashfree if subscription ID exists
            if subscription.cfSubscriptionId:
                try:
                    await self.cashfree_service.cancel_subscription(
                        subscription.cfSubscriptionId
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to cancel subscription in Cashfree",
                        extra={
                            "subscription_id": subscription_id,
                            "cf_subscription_id": subscription.cfSubscriptionId,
                            "error": str(e),
                        },
                    )

            # Update subscription status
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.updatedAt = datetime.now(UTC)
            await subscription.save()

            logger.info(
                "Subscription cancelled",
                extra={"subscription_id": subscription_id},
            )

            return {"success": True, "message": "Subscription cancelled successfully"}

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(
                "Error cancelling subscription",
                extra={"subscription_id": subscription_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_user_subscriptions(self, user_id: str) -> list[Subscription]:
        """Get all subscriptions for a user."""
        try:
            subscriptions = (
                await Subscription.find(Subscription.userId == ObjectId(user_id))
                .sort(-Subscription.createdAt)
                .to_list()
            )

            logger.info(
                "User subscriptions retrieved",
                extra={"user_id": user_id, "count": len(subscriptions)},
            )

            return subscriptions

        except Exception as e:
            logger.error(
                "Error getting user subscriptions",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def process_webhook(
        self,
        webhook_data: dict[str, Any],
        raw_body: str | None = None,
        signature: str | None = None,
    ) -> dict[str, Any]:
        """Process Cashfree subscription webhook."""
        try:
            # Note: Signature verification is already done in the endpoint before calling this method
            # No need to verify again here to avoid duplicate verification

            # Extract subscription information
            # Cashfree webhook structure varies by event type:
            # - SUBSCRIPTION_AUTH_STATUS, SUBSCRIPTION_PAYMENT_SUCCESS: cf_subscription_id directly in data
            # - SUBSCRIPTION_STATUS_CHANGED: subscription_details.subscription_id
            # - SUBSCRIPTION_ACTIVATED, SUBSCRIPTION_CHARGED: data.subscription.subscription_id
            data = webhook_data.get("data", {})
            event_type = webhook_data.get("type", "")

            # Try multiple locations for subscription ID
            cf_subscription_id = (
                data.get(
                    "cf_subscription_id"
                )  # Direct in data (AUTH_STATUS, PAYMENT_SUCCESS)
                or data.get("subscription_id")  # Alternative direct field
                or data.get("subscription_details", {}).get(
                    "subscription_id"
                )  # SUBSCRIPTION_STATUS_CHANGED
                or data.get("subscription", {}).get(
                    "subscription_id"
                )  # SUBSCRIPTION_ACTIVATED, SUBSCRIPTION_CHARGED
            )

            if not cf_subscription_id:
                # Check if this is a test webhook (has test_object in data)
                is_test_webhook = "test_object" in webhook_data.get("data", {})
                if is_test_webhook:
                    logger.info(
                        "Test webhook received (no subscription_id in test payload)",
                        extra={"webhook_type": webhook_data.get("type")},
                    )
                    return {
                        "success": True,
                        "message": "Test webhook received and verified",
                    }

                logger.warning("Subscription ID not found in webhook data")
                return {
                    "success": False,
                    "message": "Subscription ID not found in webhook payload",
                }

            # Get subscription from database
            subscription = await Subscription.find_one(
                Subscription.cfSubscriptionId == cf_subscription_id
            )

            if not subscription:
                logger.warning(
                    "Subscription not found for webhook",
                    extra={"cf_subscription_id": cf_subscription_id},
                )
                return {"success": False, "message": "Subscription not found"}

            # Update subscription status based on event type
            event_type_upper = event_type.upper()

            # Get subscription data from appropriate location based on event type
            subscription_data = (
                data.get("subscription_details", {})  # SUBSCRIPTION_STATUS_CHANGED
                or data.get(
                    "subscription", {}
                )  # SUBSCRIPTION_ACTIVATED, SUBSCRIPTION_CHARGED
                or data  # Fallback to data itself
            )

            # Check if already processed (idempotency) - prevent duplicate credit creation
            # Skip if already ACTIVE and this is a renewal/charge/activation event
            if (
                subscription.status == SubscriptionStatus.ACTIVE
                and event_type_upper
                in [
                    "SUBSCRIPTION_ACTIVATED",
                    "SUBSCRIPTION_CHARGED",
                    "SUBSCRIPTION_PAYMENT_SUCCESS",
                ]
            ):
                logger.info(
                    "Subscription already active, skipping credit activation for renewal",
                    extra={
                        "subscription_id": str(subscription.id),
                        "cf_subscription_id": cf_subscription_id,
                        "event_type": event_type,
                    },
                )
                # Still update metadata if needed, but don't activate credits again
                if (
                    subscription_data.get("current_cycle")
                    and not subscription.startDate
                ):
                    subscription.startDate = datetime.now(UTC)
                if not subscription.nextBillingDate:
                    subscription.nextBillingDate = datetime.now(UTC) + timedelta(
                        days=30
                    )
                subscription.updatedAt = datetime.now(UTC)
                await subscription.save()
                return {"success": True, "message": "Already processed"}

            # Handle different event types
            # SUBSCRIPTION_ACTIVATED, SUBSCRIPTION_CHARGED, SUBSCRIPTION_PAYMENT_SUCCESS, SUBSCRIPTION_STATUS_CHANGED (with active status)
            if event_type_upper in [
                "SUBSCRIPTION_ACTIVATED",
                "SUBSCRIPTION_CHARGED",
                "SUBSCRIPTION_PAYMENT_SUCCESS",
            ]:
                subscription.status = SubscriptionStatus.ACTIVE
                if not subscription.startDate:
                    subscription.startDate = datetime.now(UTC)
                # Calculate next billing date (assuming monthly for now)
                if not subscription.nextBillingDate:
                    subscription.nextBillingDate = datetime.now(UTC) + timedelta(
                        days=30
                    )

                # Activate credits on activation or payment success
                await self._activate_credits_for_subscription(subscription)
            elif event_type_upper == "SUBSCRIPTION_STATUS_CHANGED":
                # Capture previous status before any modifications to detect real transitions
                previous_status = subscription.status

                # Check subscription status from subscription_details
                # subscription_data is already set to data.get("subscription_details", {}) above
                subscription_status = subscription_data.get("status", "").upper()

                # If status is not found in subscription_details, check if subscription is being activated
                # For SUBSCRIPTION_STATUS_CHANGED, if status is empty but we're processing it,
                # it might mean the subscription is being activated (transitioning from initialized to active)
                if subscription_status == "ACTIVE":
                    subscription.status = SubscriptionStatus.ACTIVE
                    if not subscription.startDate:
                        subscription.startDate = datetime.now(UTC)
                    if not subscription.nextBillingDate:
                        subscription.nextBillingDate = datetime.now(UTC) + timedelta(
                            days=30
                        )
                elif subscription_status == "CANCELLED":
                    subscription.status = SubscriptionStatus.CANCELLED
                elif subscription_status == "EXPIRED":
                    subscription.status = SubscriptionStatus.EXPIRED
                elif not subscription_status:
                    # Empty status in SUBSCRIPTION_STATUS_CHANGED webhook - do not auto-activate
                    # This could indicate malformed webhook, incomplete data, or initialization phase
                    # Wait for explicit SUBSCRIPTION_ACTIVATED event or status="ACTIVE" in webhook
                    logger.warning(
                        "SUBSCRIPTION_STATUS_CHANGED received with empty status field",
                        extra={
                            "subscription_id": str(subscription.id),
                            "cf_subscription_id": cf_subscription_id,
                            "current_status": subscription.status,
                            "event_type": event_type,
                            "webhook_data": webhook_data,
                        },
                    )
                    # Keep current status - do not auto-activate based on empty status
                    # Subscription will be activated via explicit SUBSCRIPTION_ACTIVATED event
                # If status is unknown/invalid, keep current status but still process the webhook

                # Activate credits only on real transition to ACTIVE (not if already ACTIVE)
                if (
                    subscription.status == SubscriptionStatus.ACTIVE
                    and previous_status != SubscriptionStatus.ACTIVE
                ):
                    await self._activate_credits_for_subscription(subscription)
            elif event_type_upper == "SUBSCRIPTION_CANCELLED":
                subscription.status = SubscriptionStatus.CANCELLED
            elif event_type_upper == "SUBSCRIPTION_EXPIRED":
                subscription.status = SubscriptionStatus.EXPIRED

            subscription.updatedAt = datetime.now(UTC)
            await subscription.save()

            logger.info(
                "Subscription webhook processed",
                extra={
                    "subscription_id": str(subscription.id),
                    "cf_subscription_id": cf_subscription_id,
                    "event_type": event_type,
                    "status": subscription.status,
                },
            )

            return {"success": True, "message": "Webhook processed"}

        except Exception as e:
            logger.error(
                "Error processing subscription webhook",
                extra={"webhook_data": webhook_data, "error": str(e)},
                exc_info=True,
            )
            return {"success": False, "message": str(e)}

    async def _activate_credits_for_subscription(
        self, subscription: Subscription
    ) -> None:
        """Activate credits for an active subscription."""
        try:
            # Get plan
            plan = await Plan.find_one(Plan.id == subscription.planId)

            if not plan:
                logger.warning(
                    "Plan not found for subscription",
                    extra={"subscription_id": str(subscription.id)},
                )
                return

            # Calculate expiry date based on plan duration
            expires_at = None
            if plan.durationInDays > 0:
                expires_at = datetime.now(UTC) + timedelta(days=plan.durationInDays)

            # Create credit record
            await self.credit_service.create_credit(
                user_id=subscription.userId,
                credit_type=CreditType.PERIODIC,
                credits=plan.credits,
                expires_at=expires_at,
            )

            logger.info(
                "Credits activated for subscription",
                extra={
                    "subscription_id": str(subscription.id),
                    "user_id": str(subscription.userId),
                    "credits": plan.credits,
                },
            )

        except Exception as e:
            logger.error(
                "Error activating credits for subscription",
                extra={"subscription_id": str(subscription.id), "error": str(e)},
                exc_info=True,
            )
