from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import Any

from app.core.config import settings
from app.core.logging import sanitize_log_data
from app.core.resilience import ResilientHttpClient

logger = logging.getLogger(__name__)


class CashfreeService:
    """Service for Cashfree payment gateway integration."""

    def __init__(self):
        self.name = "CashfreeService"
        self.client = ResilientHttpClient(
            timeout_seconds=30,
            circuit_key="cashfree_api",
        )
        self.base_url = settings.CASHFREE_BASE_URL
        self.app_id = settings.CASHFREE_APP_ID
        self.secret_key = settings.CASHFREE_SECRET_KEY
        self.api_version = settings.CASHFREE_API_VERSION
        self.webhook_secret = settings.CASHFREE_WEBHOOK_SECRET

    def _get_headers(self) -> dict[str, str]:
        """Get Cashfree API headers."""
        return {
            "Content-Type": "application/json",
            "x-client-id": self.app_id,
            "x-client-secret": self.secret_key,
            "x-api-version": self.api_version,
        }

    def _get_price_with_gst(self, price: float) -> float:
        """Calculate price with GST."""
        return round(price * (1 + settings.GST_RATE), 2)

    async def create_payment_order(
        self,
        order_id: str,
        amount: float,
        customer_details: dict[str, Any],
        order_meta: dict[str, Any],
        order_tags: dict[str, Any],
        order_note: str,
    ) -> dict[str, Any]:
        """Create a payment order in Cashfree."""
        try:
            amount_with_gst = self._get_price_with_gst(amount)

            payload = {
                "order_id": order_id,
                "order_amount": amount_with_gst,
                "order_currency": "INR",
                "order_note": order_note,
                "customer_details": customer_details,
                "order_meta": order_meta,
                "order_tags": order_tags,
            }

            logger.info(
                "Creating Cashfree payment order",
                extra={
                    "order_id": order_id,
                    "amount": amount_with_gst,
                    "customer_id": customer_details.get("customer_id"),
                },
            )

            response = await self.client.request(
                "POST",
                f"{self.base_url}/orders",
                json=payload,
                headers=self._get_headers(),
                circuit_key="cashfree_api",
            )

            response_data = response.json()

            logger.info(
                "Cashfree payment order created",
                extra={
                    "order_id": order_id,
                    "cf_order_id": response_data.get("cf_order_id"),
                    "payment_session_id": response_data.get("payment_session_id"),
                },
            )

            return response_data

        except Exception as e:
            logger.error(
                "Failed to create Cashfree payment order",
                extra={"order_id": order_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_order_details(self, order_id: str) -> dict[str, Any] | None:
        """Get order details from Cashfree."""
        try:
            logger.info("Fetching Cashfree order details", extra={"order_id": order_id})

            response = await self.client.request(
                "GET",
                f"{self.base_url}/orders/{order_id}",
                headers=self._get_headers(),
                circuit_key="cashfree_api",
            )

            response_data = response.json()

            logger.info(
                "Cashfree order details fetched",
                extra={
                    "order_id": order_id,
                    "order_status": response_data.get("order_status"),
                },
            )

            return response_data

        except Exception as e:
            logger.error(
                "Failed to fetch Cashfree order details",
                extra={"order_id": order_id, "error": str(e)},
                exc_info=True,
            )
            return None

    async def create_cashfree_plan(
        self,
        plan_id: str,
        plan_name: str,
        plan_type: str,
        plan_amount: float,
        plan_note: str,
        plan_interval_type: str = "WEEK",
        plan_intervals: int = 4,
    ) -> dict[str, Any]:
        """Create a plan in Cashfree."""
        try:
            amount_with_gst = self._get_price_with_gst(plan_amount)

            plan_data = {
                "plan_id": plan_id,
                "plan_name": plan_name,
                "plan_type": plan_type,  # ON_DEMAND or PERIODIC
                "plan_max_amount": amount_with_gst,
                "plan_recurring_amount": amount_with_gst,
                "plan_note": plan_note,
                "plan_max_cycles": 0,  # 0 for unlimited
                "plan_interval_type": plan_interval_type,
                "plan_intervals": plan_intervals,
                "plan_currency": "INR",
            }

            logger.info(
                "Creating Cashfree plan",
                extra={
                    "plan_id": plan_id,
                    "plan_name": plan_name,
                    "plan_type": plan_type,
                },
            )

            response = await self.client.request(
                "POST",
                f"{self.base_url}/plans",
                json=plan_data,
                headers=self._get_headers(),
                circuit_key="cashfree_api",
            )

            response_data = response.json()

            if "plan_id" in response_data:
                logger.info(
                    "Cashfree plan created",
                    extra={
                        "plan_id": plan_id,
                        "cf_plan_id": response_data.get("plan_id"),
                    },
                )
            else:
                logger.warning(
                    "Cashfree plan creation may have failed",
                    extra={
                        "plan_id": plan_id,
                        "response": sanitize_log_data(response_data),
                    },
                )

            return response_data

        except Exception as e:
            logger.error(
                "Failed to create Cashfree plan",
                extra={"plan_id": plan_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def create_subscription(
        self,
        subscription_id: str,
        customer_details: dict[str, Any],
        plan_id: str,
        subscription_meta: dict[str, Any],
        subscription_expiry_time: str,
        subscription_first_charge_time: str,
        subscription_tags: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a subscription in Cashfree."""
        try:
            subscription_data = {
                "subscription_id": subscription_id,
                "customer_details": customer_details,
                "plan_details": {"plan_id": plan_id},
                "authorization_details": {
                    "authorization_amount": 1,
                    "authorization_amount_refund": True,
                    "payment_methods": ["enach", "pnach", "upi", "card"],
                },
                "subscription_meta": subscription_meta,
                "subscription_expiry_time": subscription_expiry_time,
                "subscription_first_charge_time": subscription_first_charge_time,
                "subscription_tags": subscription_tags,
            }

            logger.info(
                "Creating Cashfree subscription",
                extra={
                    "subscription_id": subscription_id,
                    "plan_id": plan_id,
                    "customer_id": customer_details.get("customer_email"),
                },
            )

            response = await self.client.request(
                "POST",
                f"{self.base_url}/subscriptions",
                json=subscription_data,
                headers=self._get_headers(),
                circuit_key="cashfree_api",
            )

            response_data = response.json()

            if response.status_code == 200 and "subscription_id" in response_data:
                logger.info(
                    "Cashfree subscription created",
                    extra={
                        "subscription_id": subscription_id,
                        "cf_subscription_id": response_data.get("subscription_id"),
                    },
                )
            else:
                logger.warning(
                    "Cashfree subscription creation may have failed",
                    extra={
                        "subscription_id": subscription_id,
                        "response": sanitize_log_data(response_data),
                    },
                )

            return response_data

        except Exception as e:
            logger.error(
                "Failed to create Cashfree subscription",
                extra={"subscription_id": subscription_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_subscription_details(
        self, subscription_id: str
    ) -> dict[str, Any] | None:
        """Get subscription details from Cashfree."""
        try:
            logger.info(
                "Fetching Cashfree subscription details",
                extra={"subscription_id": subscription_id},
            )

            response = await self.client.request(
                "GET",
                f"{self.base_url}/subscriptions/{subscription_id}",
                headers=self._get_headers(),
                circuit_key="cashfree_api",
            )

            response_data = response.json()

            logger.info(
                "Cashfree subscription details fetched",
                extra={
                    "subscription_id": subscription_id,
                    "subscription_status": response_data.get("subscription_status"),
                },
            )

            return response_data

        except Exception as e:
            logger.error(
                "Failed to fetch Cashfree subscription details",
                extra={"subscription_id": subscription_id, "error": str(e)},
                exc_info=True,
            )
            return None

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Cancel a subscription in Cashfree."""
        try:
            subscription_data = {
                "action": "CANCEL",
                "subscription_id": subscription_id,
            }

            logger.info(
                "Cancelling Cashfree subscription",
                extra={"subscription_id": subscription_id},
            )

            response = await self.client.request(
                "POST",
                f"{self.base_url}/subscriptions/{subscription_id}/manage",
                json=subscription_data,
                headers=self._get_headers(),
                circuit_key="cashfree_api",
            )

            response_data = response.json()

            if response.status_code == 200:
                logger.info(
                    "Cashfree subscription cancelled",
                    extra={"subscription_id": subscription_id},
                )
            else:
                logger.warning(
                    "Cashfree subscription cancellation may have failed",
                    extra={
                        "subscription_id": subscription_id,
                        "response": sanitize_log_data(response_data),
                    },
                )

            return response_data

        except Exception as e:
            logger.error(
                "Failed to cancel Cashfree subscription",
                extra={"subscription_id": subscription_id, "error": str(e)},
                exc_info=True,
            )
            raise

    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """Verify Cashfree webhook signature using HMAC-SHA256."""
        try:
            if not self.webhook_secret:
                logger.warning(
                    "Webhook secret not configured, skipping signature verification"
                )
                # Only allow bypass in development/testing with explicit flag
                if settings.WEBHOOK_SIGNATURE_BYPASS:
                    logger.warning(
                        "Webhook signature bypass enabled (development mode only)",
                        extra={"environment": settings.ENVIRONMENT},
                    )
                    return True
                return False  # Treat missing secret as invalid

            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Use constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(expected_signature, signature)

            if not is_valid:
                logger.warning(
                    "Webhook signature verification failed",
                    extra={
                        "expected_signature": expected_signature[:8] + "...",
                        "received_signature": signature[:8] + "...",
                    },
                )

            return is_valid

        except Exception as e:
            logger.error(
                "Error verifying webhook signature",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    def generate_order_id(self) -> str:
        """Generate a unique order ID."""
        return f"order_{uuid.uuid4().hex[:10]}"

    def generate_subscription_id(self) -> str:
        """Generate a unique subscription ID."""
        return f"sub_{uuid.uuid4().hex[:10]}"
