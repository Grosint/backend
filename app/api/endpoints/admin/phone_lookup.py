"""
Admin Debug Endpoints for Phone Lookup Services

This module provides admin-only endpoints for debugging and testing
individual phone lookup API services without going through the full
orchestration, database persistence, or billing logic.

Endpoints:
- POST /admin/debug/phone-lookup/{service} - Test individual phone lookup service
- POST /admin/debug/phone-lookup/all - Test all phone lookup services
- GET /admin/debug/phone-lookup/{service}/health - Quick health check for a service
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas.admin import (
    PhoneLookupDebugRequest,
    ServiceTestResponse,
)
from app.schemas.response import SuccessResponse
from app.services.integrations.phone_lookup.aitan_service import AITANService
from app.services.integrations.phone_lookup.befisc_service import BefiscService
from app.services.integrations.phone_lookup.callapp_service import CallAppService
from app.services.integrations.phone_lookup.eyecon_service import EyeconService
from app.services.integrations.phone_lookup.hlr_service import HLRService
from app.services.integrations.phone_lookup.ignorant_service import IgnorantService
from app.services.integrations.phone_lookup.leakcheck_service import LeakCheckService
from app.services.integrations.phone_lookup.skype_service import SkypeService
from app.services.integrations.phone_lookup.telegram_service import TelegramService
from app.services.integrations.phone_lookup.truecaller_service import TrueCallerService
from app.services.integrations.phone_lookup.viewcaller_service import ViewCallerService
from app.services.integrations.phone_lookup.whatsapp_service import WhatsAppService

router = APIRouter()
logger = logging.getLogger(__name__)

# Service registry for easy access
PHONE_LOOKUP_SERVICES = {
    "truecaller": TrueCallerService,
    "eyecon": EyeconService,
    "callapp": CallAppService,
    "viewcaller": ViewCallerService,
    "whatsapp": WhatsAppService,
    "telegram": TelegramService,
    "skype": SkypeService,
    "ignorant": IgnorantService,
    "leakcheck": LeakCheckService,
    "hlr": HLRService,
    "aitan": AITANService,
    "befisc": BefiscService,
}


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

    Available services: truecaller, eyecon, callapp, viewcaller, whatsapp, telegram, skype, ignorant, leakcheck, hlr, aitan, befisc
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
        # AITAN and Befisc services require lookup_type parameter, default to "phone-lookup"
        if service_name_lower in ["aitan", "befisc"]:
            result = await service.search_phone(
                request.country_code, request.phone, "phone-lookup"
            )
        else:
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
        # AITAN and Befisc services require lookup_type parameter
        tasks = {}
        for name, service in services.items():
            if name in ["aitan", "befisc"]:
                tasks[name] = service.search_phone(
                    request.country_code, request.phone, "phone-lookup"
                )
            else:
                tasks[name] = service.search_phone(request.country_code, request.phone)

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
async def check_phone_service_health(
    service_name: str,
    test_phone: str = Query(
        "234567890", description="Test phone number (without country code)"
    ),
):
    """
    Quick health check for a phone lookup service using a test phone number.
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
        # AITAN and Befisc services require lookup_type parameter
        if service_name_lower in ["aitan", "befisc"]:
            result = await service.search_phone("+1", test_phone, "phone-lookup")
        else:
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
