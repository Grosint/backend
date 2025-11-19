"""
Admin Debug Endpoints for Testing Individual APIs

This module provides admin-only endpoints for debugging and testing
individual external API services without going through the full
orchestration, database persistence, or billing logic.

Endpoints:
- POST /admin/debug/phone-lookup/{service} - Test individual phone lookup service
- POST /admin/debug/phone-lookup/all - Test all phone lookup services
- GET /admin/debug/services - List all available services
- GET /admin/debug/phone-lookup/{service}/health - Quick health check for a service

All endpoints bypass normal business logic. Authorization removed for debugging purposes.

IMPORTANT FOR NEW API SERVICES:
================================
When adding a new API service for debugging, ensure the service's search_phone() method
includes the raw API response in the return dictionary with the key "_raw_response".

Example:
    data = response.json()
    raw_response = data  # Store raw response BEFORE any processing/formatting

    # ... process and format data ...

    return {
        "found": True,
        "source": "service_name",
        "data": formatted_data,
        "confidence": 0.9,
        "_raw_response": raw_response  # <-- REQUIRED for admin debug endpoints
    }

This allows the admin debug endpoints to return the unformatted API response when
include_raw_response=True is set in the request, which is essential for debugging
API integration issues.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Authorization removed for debugging purposes
# from app.core.auth_dependencies import require_admin_role, TokenData
from app.external_apis.phone_lookup.callapp_service import CallAppService
from app.external_apis.phone_lookup.eyecon_service import EyeconService
from app.external_apis.phone_lookup.truecaller_service import TrueCallerService
from app.external_apis.phone_lookup.viewcaller_service import ViewCallerService
from app.external_apis.phone_lookup.whatsapp_service import WhatsAppService
from app.schemas.response import SuccessResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Service registry for easy access
PHONE_LOOKUP_SERVICES = {
    "truecaller": TrueCallerService,
    "eyecon": EyeconService,
    "callapp": CallAppService,
    "viewcaller": ViewCallerService,
    "whatsapp": WhatsAppService,
}


class PhoneLookupDebugRequest(BaseModel):
    """Request model for phone lookup debug endpoint"""

    country_code: str = Field(..., description="Country code (e.g., '+1', '+91')")
    phone: str = Field(..., description="Phone number without country code")
    include_raw_response: bool = Field(False, description="Include raw API response")


class ServiceTestResponse(BaseModel):
    """Response model for individual service test"""

    service_name: str
    success: bool
    execution_time_ms: float
    found: bool | None = None
    data: dict[str, Any] | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None


@router.get("/services", response_model=SuccessResponse[dict[str, Any]])
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
        # Add other service types as they're implemented
        # "domain": {...},
        # "email": {...},
    }

    return SuccessResponse[dict[str, Any]](
        data=services,
        success=True,
        message="Available debug services retrieved successfully",
    )


@router.post(
    "/phone-lookup/{service_name}", response_model=SuccessResponse[ServiceTestResponse]
)
async def test_phone_lookup_service(
    service_name: str,
    request: PhoneLookupDebugRequest,
):
    """
    Test a single phone lookup service directly.

    This endpoint:
    - Bypasses orchestration and database
    - Calls the service directly
    - Returns detailed debugging information
    - Does NOT create search records or deduct credits

    Available services: truecaller, eyecon, callapp, viewcaller, whatsapp
    """
    service_name_lower = service_name.lower()

    if service_name_lower not in PHONE_LOOKUP_SERVICES:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' not found. Available: {', '.join(PHONE_LOOKUP_SERVICES.keys())}",
        )

    try:
        logger.info(
            f"Admin debug: Testing {service_name_lower} for {request.country_code}{request.phone}"
        )

        # Initialize service
        service_class = PHONE_LOOKUP_SERVICES[service_name_lower]
        service = service_class()

        # Measure execution time
        start_time = time.time()

        # Call service directly
        result = await service.search_phone(request.country_code, request.phone)
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Build response
        is_success = (
            not isinstance(result, Exception)
            and isinstance(result, dict)
            and not result.get("error")
        )

        # Extract raw response from service result (services include _raw_response field)
        raw_response = None
        if request.include_raw_response and isinstance(result, dict):
            raw_response = result.get("_raw_response")

        response_data = ServiceTestResponse(
            service_name=service_name_lower,
            success=is_success,
            execution_time_ms=round(execution_time, 2),
            found=result.get("found") if isinstance(result, dict) else None,
            data=result if isinstance(result, dict) else None,
            error=str(result) if isinstance(result, Exception) else result.get("error"),
            raw_response=raw_response,
        )

        logger.info(
            f"Admin debug: {service_name_lower} completed in {execution_time:.2f}ms"
        )

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message=f"Service '{service_name}' tested successfully",
        )

    except Exception as e:
        logger.error(f"Admin debug: {service_name_lower} failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service test failed: {str(e)}"
        ) from e


@router.post("/phone-lookup/all", response_model=SuccessResponse[dict[str, Any]])
async def test_all_phone_lookup_services(
    request: PhoneLookupDebugRequest,
):
    """
    Test all phone lookup services in parallel.

    Useful for:
    - Comparing service performance
    - Identifying which services are failing
    - Quick health check of all services

    Returns results from all services with timing information.
    """
    try:
        logger.info(
            f"Admin debug: Testing all phone lookup services for {request.country_code}{request.phone}"
        )

        # Initialize all services
        services = {
            name: service_class()
            for name, service_class in PHONE_LOOKUP_SERVICES.items()
        }

        # Create tasks for parallel execution
        tasks = {
            name: service.search_phone(request.country_code, request.phone)
            for name, service in services.items()
        }

        # Measure total execution time
        start_time = time.time()

        # Execute all services in parallel
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        total_execution_time = (time.time() - start_time) * 1000

        # Build response for each service
        service_results = {}
        service_names = list(services.keys())

        for service_name, result in zip(service_names, results, strict=False):
            if isinstance(result, Exception):
                service_results[service_name] = {
                    "success": False,
                    "error": str(result),
                    "found": None,
                    "data": None,
                }
            else:
                is_success = isinstance(result, dict) and not result.get("error")
                # Extract raw response if requested
                raw_response = None
                if request.include_raw_response and isinstance(result, dict):
                    raw_response = result.get("_raw_response")

                service_results[service_name] = {
                    "success": is_success,
                    "found": result.get("found") if isinstance(result, dict) else None,
                    "data": result if request.include_raw_response else None,
                    "error": result.get("error") if isinstance(result, dict) else None,
                    "raw_response": raw_response,
                }

        # Calculate summary
        successful = sum(1 for r in service_results.values() if r["success"])
        total = len(service_results)

        response_data = {
            "phone": f"{request.country_code}{request.phone}",
            "total_execution_time_ms": round(total_execution_time, 2),
            "summary": {
                "total_services": total,
                "successful_services": successful,
                "failed_services": total - successful,
            },
            "services": service_results,
        }

        logger.info(
            f"Admin debug: All services tested - {successful}/{total} successful in {total_execution_time:.2f}ms"
        )

        return SuccessResponse[dict[str, Any]](
            data=response_data,
            success=True,
            message=f"All services tested: {successful}/{total} successful",
        )

    except Exception as e:
        logger.error("Admin debug: Testing all services failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service testing failed: {str(e)}"
        ) from e


@router.get(
    "/phone-lookup/{service_name}/health",
    response_model=SuccessResponse[dict[str, Any]],
)
async def check_service_health(
    service_name: str,
    test_phone: str = Query(
        "234567890", description="Test phone number (without country code)"
    ),
):
    """
    Quick health check for a service using a test phone number.
    Returns basic connectivity and response time information.
    """
    service_name_lower = service_name.lower()

    if service_name_lower not in PHONE_LOOKUP_SERVICES:
        raise HTTPException(
            status_code=404, detail=f"Service '{service_name}' not found"
        )

    try:
        service_class = PHONE_LOOKUP_SERVICES[service_name_lower]
        service = service_class()

        start_time = time.time()
        result = await service.search_phone("+1", test_phone)  # Use test number
        execution_time = (time.time() - start_time) * 1000

        is_healthy = (
            isinstance(result, dict)
            and not result.get("error")
            and not isinstance(result, Exception)
        )

        return SuccessResponse[dict[str, Any]](
            data={
                "service": service_name_lower,
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time_ms": round(execution_time, 2),
                "has_error": bool(
                    result.get("error") if isinstance(result, dict) else False
                ),
            },
            success=True,
            message=f"Health check completed for {service_name}",
        )

    except Exception as e:
        logger.error(
            f"Admin debug: Health check failed for {service_name_lower}", exc_info=True
        )
        return SuccessResponse[dict[str, Any]](
            data={
                "service": service_name_lower,
                "status": "unhealthy",
                "error": str(e),
            },
            success=False,
            message=f"Health check failed for {service_name}",
        )
