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
                "return_url": f"{origin}/api/v1/subscriptions/redirect/{subscription_id}",
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

            # Extract subscription information
            subscription_data = webhook_data.get("data", {}).get("subscription", {})
            cf_subscription_id = subscription_data.get("subscription_id")
            if not cf_subscription_id:
                logger.warning("Subscription ID not found in webhook data")
                return {"success": False, "message": "Subscription ID not found"}

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
            event_type = webhook_data.get("type", "").upper()

            if event_type in ["SUBSCRIPTION_ACTIVATED", "SUBSCRIPTION_CHARGED"]:
                subscription.status = SubscriptionStatus.ACTIVE
                if subscription_data.get("current_cycle"):
                    subscription.startDate = datetime.now(UTC)
                    # Calculate next billing date (assuming monthly for now)
                    subscription.nextBillingDate = datetime.now(UTC) + timedelta(
                        days=30
                    )

                # Activate credits on activation or renewal
                await self._activate_credits_for_subscription(subscription)

            elif event_type == "SUBSCRIPTION_CANCELLED":
                subscription.status = SubscriptionStatus.CANCELLED
            elif event_type == "SUBSCRIPTION_EXPIRED":
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
