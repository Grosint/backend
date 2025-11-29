"""
Admin Debug Endpoint for Listing Available Services

This module provides an endpoint to list all available services for debugging.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints.admin.email_lookup import EMAIL_LOOKUP_SERVICES
from app.api.endpoints.admin.phone_lookup import PHONE_LOOKUP_SERVICES
from app.schemas.response import SuccessResponse

router = APIRouter()


@router.get("/services", response_model=SuccessResponse[dict])
async def list_available_services():
    """
    List all available services for debugging.
    Returns a catalog of all testable services grouped by type.
    """
    services = {
        "phone_lookup": {
            "services": list(PHONE_LOOKUP_SERVICES.keys()),
            "description": "Phone number lookup services",
        },
        "email_lookup": {
            "services": list(EMAIL_LOOKUP_SERVICES.keys()),
            "description": "Email address lookup services",
        },
        # Add other service types as they're implemented
        # "domain": {...},
    }

    return SuccessResponse[dict](
        data=services,
        success=True,
        message="Available debug services retrieved successfully",
    )
