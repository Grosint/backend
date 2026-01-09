"""Subscription API endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.core.exceptions import AuthorizationException, NotFoundException
from app.models.subscription import Subscription
from app.schemas.response import SuccessResponse
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionCreateResponse,
    SubscriptionResponse,
)
from app.services.subscription_service import SubscriptionService
from app.utils.webhook import (
    create_webhook_error_response,
    create_webhook_response,
    extract_webhook_data,
    verify_webhook_signature,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/create", response_model=SuccessResponse[SubscriptionCreateResponse])
async def create_subscription(
    subscription_data: SubscriptionCreate,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Create a subscription for periodic payment."""
    try:
        subscription_service = SubscriptionService(db)

        result = await subscription_service.create_subscription(
            user_id=current_user.user_id,
            plan_id=subscription_data.planId,
            origin=subscription_data.origin,
        )

        logger.info(
            "Subscription created",
            extra={
                "user_id": current_user.user_id,
                "plan_id": subscription_data.planId,
                "cf_subscription_id": result["cashfreeSubscriptionId"],
            },
        )

        return SuccessResponse(
            message="Subscription created successfully",
            data=SubscriptionCreateResponse(
                cashfreeSubscriptionId=result["cashfreeSubscriptionId"],
                subscriptionSessionId=result["subscriptionSessionId"],
                redirectUrl=result.get("redirectUrl"),
            ),
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(
            "Error creating subscription",
            extra={
                "user_id": current_user.user_id,
                "plan_id": subscription_data.planId,
                "error": str(e),
            },
            exc_info=True,
        )
        raise


@router.get("/me", response_model=SuccessResponse[list[SubscriptionResponse]])
async def get_user_subscriptions(
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Get all subscriptions for the current user."""
    try:
        subscription_service = SubscriptionService(db)
        subscriptions = await subscription_service.get_user_subscriptions(
            current_user.user_id
        )

        subscription_responses = [
            SubscriptionResponse(
                id=str(sub.id),
                userId=str(sub.userId),
                planId=str(sub.planId),
                cfSubscriptionId=sub.cfSubscriptionId,
                status=sub.status,
                startDate=sub.startDate,
                nextBillingDate=sub.nextBillingDate,
                createdAt=sub.createdAt,
                updatedAt=sub.updatedAt,
            )
            for sub in subscriptions
        ]

        logger.info(
            "User subscriptions retrieved",
            extra={
                "user_id": current_user.user_id,
                "count": len(subscription_responses),
            },
        )

        return SuccessResponse(
            message="Subscriptions retrieved successfully",
            data=subscription_responses,
        )

    except Exception as e:
        logger.error(
            "Error getting user subscriptions",
            extra={"user_id": current_user.user_id, "error": str(e)},
            exc_info=True,
        )
        raise


@router.get("/{subscription_id}", response_model=SuccessResponse[SubscriptionResponse])
async def get_subscription(
    subscription_id: str,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Get a single subscription by ID."""
    try:
        # Load subscription to verify ownership
        subscription = await Subscription.find_one(
            Subscription.id == ObjectId(subscription_id)
        )
        if not subscription:
            raise NotFoundException(
                resource="Subscription", resource_id=subscription_id
            )

        # Verify ownership - check if subscription belongs to current user
        if str(subscription.userId) != current_user.user_id:
            logger.warning(
                "Unauthorized subscription access attempt",
                extra={
                    "user_id": current_user.user_id,
                    "subscription_id": subscription_id,
                    "subscription_owner_id": str(subscription.userId),
                },
            )
            raise AuthorizationException(
                message="You do not have permission to access this subscription"
            )

        subscription_response = SubscriptionResponse(
            id=str(subscription.id),
            userId=str(subscription.userId),
            planId=str(subscription.planId),
            cfSubscriptionId=subscription.cfSubscriptionId,
            status=subscription.status,
            startDate=subscription.startDate,
            nextBillingDate=subscription.nextBillingDate,
            createdAt=subscription.createdAt,
            updatedAt=subscription.updatedAt,
        )

        logger.info(
            "Subscription retrieved",
            extra={"user_id": current_user.user_id, "subscription_id": subscription_id},
        )

        return SuccessResponse(
            message="Subscription retrieved successfully",
            data=subscription_response,
        )

    except (NotFoundException, AuthorizationException):
        raise
    except Exception as e:
        logger.error(
            "Error getting subscription",
            extra={"subscription_id": subscription_id, "error": str(e)},
            exc_info=True,
        )
        raise


@router.post("/{subscription_id}/cancel", response_model=SuccessResponse[dict])
async def cancel_subscription(
    subscription_id: str,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Cancel a subscription."""
    try:
        # Load subscription to verify ownership
        subscription = await Subscription.find_one(
            Subscription.id == ObjectId(subscription_id)
        )
        if not subscription:
            raise NotFoundException(
                resource="Subscription", resource_id=subscription_id
            )

        # Verify ownership - check if subscription belongs to current user
        if str(subscription.userId) != current_user.user_id:
            logger.warning(
                "Unauthorized subscription cancellation attempt",
                extra={
                    "user_id": current_user.user_id,
                    "subscription_id": subscription_id,
                    "subscription_owner_id": str(subscription.userId),
                },
            )
            raise AuthorizationException(
                message="You do not have permission to cancel this subscription"
            )

        # Ownership verified - proceed with cancellation
        subscription_service = SubscriptionService(db)
        result = await subscription_service.cancel_subscription(subscription_id)

        logger.info(
            "Subscription cancelled",
            extra={"user_id": current_user.user_id, "subscription_id": subscription_id},
        )

        return SuccessResponse(
            message="Subscription cancelled successfully",
            data=result,
        )

    except (NotFoundException, AuthorizationException):
        raise
    except Exception as e:
        logger.error(
            "Error cancelling subscription",
            extra={"subscription_id": subscription_id, "error": str(e)},
            exc_info=True,
        )
        raise


@router.post("/redirect/{subscription_id}", response_class=HTMLResponse)
async def subscription_redirect(subscription_id: str, db=Depends(get_database)):
    """Redirect page after subscription authorization."""
    try:
        # Optionally verify subscription status when page loads (for eventual consistency)
        try:
            # Try to find subscription by ID or cfSubscriptionId
            subscription = None
            # First, try to query by ObjectId if subscription_id is a valid ObjectId
            try:
                object_id = ObjectId(subscription_id)
                subscription = await Subscription.find_one(Subscription.id == object_id)
            except InvalidId:
                # If not a valid ObjectId, skip to cfSubscriptionId query
                pass

            # If not found by ID, try by cfSubscriptionId
            if not subscription:
                subscription = await Subscription.find_one(
                    Subscription.cfSubscriptionId == subscription_id
                )
            if subscription:
                logger.info(
                    "Subscription found on redirect page load",
                    extra={
                        "subscription_id": subscription_id,
                        "status": subscription.status,
                    },
                )
        except Exception as verify_error:
            # Log but don't fail - webhook will handle verification
            logger.warning(
                "Could not verify subscription on redirect page load",
                extra={"subscription_id": subscription_id, "error": str(verify_error)},
            )

        # Read the redirect.html file
        # Path from app/api/endpoints/ to app/static/
        app_dir = Path(__file__).parent.parent.parent
        html_file = app_dir / "static" / "redirect.html"

        if not html_file.exists():
            logger.error("Redirect HTML file not found", extra={"path": str(html_file)})
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Redirect page not available",
            )

        with open(html_file, encoding="utf-8") as f:
            html_content = f.read()

        logger.info(
            "Subscription redirect page served",
            extra={"subscription_id": subscription_id},
        )

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(
            "Error serving redirect page",
            extra={"subscription_id": subscription_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error loading redirect page",
        ) from e


@router.post("/webhook")
async def subscription_webhook(
    request: Request,
    x_webhook_signature: str | None = Header(None, alias="x-webhook-signature"),
    x_webhook_timestamp: str | None = Header(None, alias="x-webhook-timestamp"),
    db=Depends(get_database),
):
    """Handle Cashfree subscription webhook."""
    try:
        # Extract webhook data
        webhook_data, body_str, signature = await extract_webhook_data(
            request, x_webhook_signature
        )

        # Verify signature
        subscription_service = SubscriptionService(db)
        if not verify_webhook_signature(
            body_str,
            signature,
            subscription_service.cashfree_service,
            x_webhook_timestamp,
        ):
            logger.warning("Subscription webhook signature verification failed")
            return create_webhook_response(success=False, message="Invalid signature")

        # Extract subscription ID for logging
        subscription_id = (
            webhook_data.get("data", {}).get("subscription", {}).get("subscription_id")
        )
        event_type = webhook_data.get("type")

        logger.info(
            "Subscription webhook received",
            extra={
                "subscription_id": subscription_id,
                "event_type": event_type,
            },
        )

        # Process webhook
        result = await subscription_service.process_webhook(
            webhook_data, raw_body=body_str, signature=signature
        )

        if result.get("success"):
            logger.info(
                "Subscription webhook processed successfully",
                extra={"subscription_id": subscription_id},
            )
            return create_webhook_response(success=True)
        else:
            logger.warning(
                "Subscription webhook processing failed",
                extra={"subscription_id": subscription_id, "result": result},
            )
            return create_webhook_response(
                success=False,
                message=result.get("message", "Webhook processing failed"),
            )

    except ValueError as e:
        logger.error("Invalid webhook payload", extra={"error": str(e)})
        return create_webhook_error_response("Invalid webhook payload")
    except Exception as e:
        logger.error(
            "Error processing subscription webhook",
            extra={"error": str(e)},
            exc_info=True,
        )
        return create_webhook_error_response("Error processing webhook")
