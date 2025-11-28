"""Webhook utility functions for shared webhook handling logic."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status

from app.core.config import settings
from app.services.integrations.payment.cashfree_service import CashfreeService

logger = logging.getLogger(__name__)


async def extract_webhook_data(
    request: Request, signature_header: str | None = None
) -> tuple[dict[str, Any], str, str | None]:
    """
    Extract and parse webhook data from request.

    Args:
        request: FastAPI request object
        signature_header: Webhook signature from header (x-cf-signature)

    Returns:
        Tuple of (webhook_data, raw_body_string, signature)
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        body_str = body.decode("utf-8")

        # Parse JSON payload
        webhook_data = json.loads(body_str)

        return webhook_data, body_str, signature_header

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in webhook payload", extra={"error": str(e)})
        raise ValueError("Invalid JSON payload") from e
    except Exception as e:
        logger.error(
            "Error extracting webhook data", extra={"error": str(e)}, exc_info=True
        )
        raise


def verify_webhook_signature(
    raw_body: str, signature: str | None, cashfree_service: CashfreeService
) -> bool:
    """
    Verify webhook signature using Cashfree service.

    Args:
        raw_body: Raw request body as string
        signature: Webhook signature from header
        cashfree_service: CashfreeService instance

    Returns:
        True if signature is valid, False otherwise
    """
    if not signature:
        logger.warning("Webhook signature not provided")
        # Only allow bypass in development/testing with explicit flag
        if settings.WEBHOOK_SIGNATURE_BYPASS:
            logger.warning(
                "Webhook signature bypass enabled (development mode only)",
                extra={"environment": settings.ENVIRONMENT},
            )
            return True
        return False  # Treat missing signature as invalid

    return cashfree_service.verify_webhook_signature(raw_body, signature)


def create_webhook_response(success: bool, message: str | None = None) -> JSONResponse:
    """
    Create standardized webhook response.

    Args:
        success: Whether webhook processing was successful
        message: Optional message to include

    Returns:
        JSONResponse with appropriate status code
    """
    if success:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": message or "Webhook processed successfully"},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": message or "Webhook processing failed"},
        )


def create_webhook_error_response(error_message: str) -> JSONResponse:
    """
    Create error response for webhook processing failures.

    Args:
        error_message: Error message to return

    Returns:
        JSONResponse with 500 status code
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": error_message},
    )
