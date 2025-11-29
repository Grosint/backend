"""Payment API endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.core.exceptions import NotFoundException
from app.schemas.payment import (
    PaymentCreate,
    PaymentCreateResponse,
    PaymentVerifyResponse,
)
from app.schemas.response import SuccessResponse
from app.services.payment_service import PaymentService
from app.utils.webhook import (
    create_webhook_error_response,
    create_webhook_response,
    extract_webhook_data,
    verify_webhook_signature,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/create", response_model=SuccessResponse[PaymentCreateResponse])
async def create_payment(
    payment_data: PaymentCreate,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Create a payment order for on-demand purchase."""
    try:
        payment_service = PaymentService(db)

        result = await payment_service.create_payment(
            user_id=current_user.user_id,
            plan_id=payment_data.planId,
            origin=payment_data.origin,
        )

        logger.info(
            "Payment order created",
            extra={
                "user_id": current_user.user_id,
                "plan_id": payment_data.planId,
                "order_id": result["orderId"],
            },
        )

        return SuccessResponse(
            message="Payment order created successfully",
            data=PaymentCreateResponse(
                paymentSessionId=result["paymentSessionId"],
                orderId=result["orderId"],
                redirectUrl=result.get("redirectUrl"),
            ),
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(
            "Error creating payment",
            extra={
                "user_id": current_user.user_id,
                "plan_id": payment_data.planId,
                "error": str(e),
            },
            exc_info=True,
        )
        raise


@router.post(
    "/verify/{order_id}", response_model=SuccessResponse[PaymentVerifyResponse]
)
async def verify_payment(
    order_id: str,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Verify payment status by order ID."""
    try:
        payment_service = PaymentService(db)
        result = await payment_service.verify_payment(order_id)

        logger.info(
            "Payment verified",
            extra={
                "user_id": current_user.user_id,
                "order_id": order_id,
                "status": result["status"],
            },
        )

        return SuccessResponse(
            message="Payment verified successfully",
            data=PaymentVerifyResponse(
                orderId=result["orderId"],
                status=result["status"],
                amount=result["amount"],
                paymentMethod=result.get("paymentMethod"),
                transactionTime=result.get("transactionTime"),
            ),
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(
            "Error verifying payment",
            extra={"order_id": order_id, "error": str(e)},
            exc_info=True,
        )
        raise


@router.get("/redirect/{order_id}", response_class=HTMLResponse)
async def payment_redirect(order_id: str):
    """Redirect page after payment completion."""
    try:
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

        logger.info("Payment redirect page served", extra={"order_id": order_id})

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(
            "Error serving redirect page",
            extra={"order_id": order_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error loading redirect page",
        ) from e


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    x_cf_signature: str | None = Header(None, alias="x-cf-signature"),
    db=Depends(get_database),
):
    """Handle Cashfree payment webhook."""
    try:
        # Extract webhook data
        webhook_data, body_str, signature = await extract_webhook_data(
            request, x_cf_signature
        )

        # Verify signature
        payment_service = PaymentService(db)
        if not verify_webhook_signature(
            body_str, signature, payment_service.cashfree_service
        ):
            logger.warning("Payment webhook signature verification failed")
            return create_webhook_response(success=False, message="Invalid signature")

        # Extract order ID for logging
        order_id = webhook_data.get("data", {}).get("order", {}).get("order_id")
        event_type = webhook_data.get("type")

        logger.info(
            "Payment webhook received",
            extra={
                "order_id": order_id,
                "event_type": event_type,
            },
        )

        # Process webhook
        result = await payment_service.process_webhook(
            webhook_data, raw_body=body_str, signature=signature
        )

        if result.get("success"):
            logger.info(
                "Payment webhook processed successfully",
                extra={"order_id": order_id},
            )
            return create_webhook_response(success=True)
        else:
            logger.warning(
                "Payment webhook processing failed",
                extra={"order_id": order_id, "result": result},
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
            "Error processing payment webhook",
            extra={"error": str(e)},
            exc_info=True,
        )
        return create_webhook_error_response("Error processing webhook")
