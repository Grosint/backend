"""
Admin Debug Endpoints for Email Lookup Services

This module provides admin-only endpoints for debugging and testing
individual email lookup API services without going through the full
orchestration, database persistence, or billing logic.

Endpoints:
- POST /admin/debug/email-lookup/{service} - Test individual email lookup service
- POST /admin/debug/email-lookup/all - Test all email lookup services
- POST /admin/debug/skype/search - Test Skype search by email
- GET /admin/debug/email-lookup/{service}/health - Quick health check for a service
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas.admin import (
    EmailLookupDebugRequest,
    ServiceTestResponse,
    SkypeSearchRequest,
)
from app.schemas.response import SuccessResponse
from app.services.integrations.email_lookup.ghunt import GHuntService
from app.services.integrations.email_lookup.philint import PhilINTService
from app.services.integrations.phone_lookup.leakcheck_service import LeakCheckService
from app.services.integrations.phone_lookup.skype_service import SkypeService
from app.services.orchestrators.email_lookup_orchestrator import (
    EmailLookupOrchestrator,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Email lookup service registry
EMAIL_LOOKUP_SERVICES = {
    "skype": SkypeService,
    "leakcheck": LeakCheckService,
    "ghunt": GHuntService,
    "philint": PhilINTService,
    "email_lookup": EmailLookupOrchestrator,  # Full orchestrator
}


@router.post("/skype/search", response_model=SuccessResponse[ServiceTestResponse])
async def test_skype_search(request: SkypeSearchRequest):
    """
    Test Skype search by email address.

    Note: Skype searches by email/username, not phone number.
    This endpoint allows direct testing of Skype search functionality.

    Args:
        request: SkypeSearchRequest with email address

    Returns:
        ServiceTestResponse with Skype search results
    """
    try:
        logger.info(f"Admin debug: Testing Skype search for {request.email}")

        # Initialize Skype service
        service = SkypeService()

        # Measure execution time
        start_time = time.time()

        # Call service directly (search_email method)
        result = await service.search_email(request.email)
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Build response
        is_success = (
            not isinstance(result, Exception)
            and isinstance(result, dict)
            and not result.get("error")
        )

        # Extract raw response from service result
        raw_response = None
        if request.include_raw_response and isinstance(result, dict):
            raw_response = result.get("_raw_response")

        response_data = ServiceTestResponse(
            service_name="skype",
            success=is_success,
            execution_time_ms=round(execution_time, 2),
            found=result.get("found") if isinstance(result, dict) else None,
            data=result if isinstance(result, dict) else None,
            error=str(result) if isinstance(result, Exception) else result.get("error"),
            raw_response=raw_response,
        )

        logger.info(f"Admin debug: Skype search completed in {execution_time:.2f}ms")

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message=f"Skype search for '{request.email}' completed",
        )

    except Exception as e:
        logger.error("Admin debug: Skype search failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Skype search failed: {str(e)}"
        ) from e


@router.post(
    "/email-lookup/{service_name}", response_model=SuccessResponse[ServiceTestResponse]
)
async def test_email_lookup_service(
    service_name: str,
    request: EmailLookupDebugRequest,
):
    """
    Test a single email lookup service directly.

    This endpoint:
    - Bypasses orchestration and database
    - Calls the service directly
    - Returns detailed debugging information
    - Does NOT create search records or deduct credits

    Available services: skype, leakcheck, ghunt, philint, email_lookup (full orchestrator)
    """
    service_name_lower = service_name.lower()

    if service_name_lower not in EMAIL_LOOKUP_SERVICES:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' not found. Available: {', '.join(EMAIL_LOOKUP_SERVICES.keys())}",
        )

    try:
        logger.info(f"Admin debug: Testing {service_name_lower} for {request.email}")

        # Initialize service
        service_class = EMAIL_LOOKUP_SERVICES[service_name_lower]
        service = service_class()

        # Measure execution time
        start_time = time.time()

        # Call service directly
        result = await service.search_email(request.email)
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


@router.post("/email-lookup/all", response_model=SuccessResponse[dict[str, Any]])
async def test_all_email_lookup_services(
    request: EmailLookupDebugRequest,
):
    """
    Test all email lookup services in parallel.

    Useful for:
    - Comparing service performance
    - Identifying which services are failing
    - Quick health check of all services

    Returns results from all services with timing information.
    """
    try:
        logger.info(
            f"Admin debug: Testing all email lookup services for {request.email}"
        )

        # Initialize all services
        services = {
            name: service_class()
            for name, service_class in EMAIL_LOOKUP_SERVICES.items()
        }

        # Create tasks for parallel execution
        tasks = {
            name: service.search_email(request.email)
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
            "email": request.email,
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
    "/email-lookup/{service_name}/health",
    response_model=SuccessResponse[dict[str, Any]],
)
async def check_email_service_health(
    service_name: str,
    test_email: str = Query("test@example.com", description="Test email address"),
):
    """
    Quick health check for an email lookup service using a test email.
    Returns basic connectivity and response time information.
    """
    service_name_lower = service_name.lower()

    if service_name_lower not in EMAIL_LOOKUP_SERVICES:
        raise HTTPException(
            status_code=404, detail=f"Service '{service_name}' not found"
        )

    try:
        service_class = EMAIL_LOOKUP_SERVICES[service_name_lower]
        service = service_class()

        start_time = time.time()
        result = await service.search_email(test_email)
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
