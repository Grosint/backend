"""
Admin Debug Endpoints for AITAN Service

This module provides admin-only endpoints for debugging and testing
AITAN Labs API service with different lookup types without going through the full
orchestration, database persistence, or billing logic.

Endpoints:
- POST /admin/debug/aitan/phone - Test AITAN phone lookup service
- POST /admin/debug/aitan/vehicle - Test AITAN vehicle lookup service (all methods)
- POST /admin/debug/aitan/vehicle/rc-advance - Test RC advance lookup
- POST /admin/debug/aitan/vehicle/challan-advance - Test challan advance lookup
- POST /admin/debug/aitan/vehicle/chassis-to-rc - Test chassis to RC lookup
- POST /admin/debug/aitan/vehicle/fasttag-history - Test FastTag history lookup
- GET /admin/debug/aitan/phone/health - Quick health check for phone lookup
- GET /admin/debug/aitan/vehicle/health - Quick health check for vehicle lookup
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas.admin import (
    AITANVehicleLookupRequest,
    PhoneLookupDebugRequest,
    ServiceTestResponse,
)
from app.schemas.response import SuccessResponse
from app.services.integrations.phone_lookup.aitan import AITANService

router = APIRouter()
logger = logging.getLogger(__name__)


def _strip_raw_from_data(data: Any) -> Any:
    """Recursively remove _raw_response and _raw_data from data (exposed at raw_response level)."""
    if isinstance(data, dict):
        return {
            k: _strip_raw_from_data(v)
            for k, v in data.items()
            if k not in ("_raw_response", "_raw_data")
        }
    if isinstance(data, list):
        return [_strip_raw_from_data(item) for item in data]
    return data


# Phone Lookup Endpoints
@router.post("/phone", response_model=SuccessResponse[ServiceTestResponse])
async def test_aitan_phone_lookup(request: PhoneLookupDebugRequest):
    """
    Test AITAN phone lookup service.

    This endpoint:
    - Bypasses orchestration and database
    - Calls the service directly
    - Returns detailed debugging information
    - Does NOT create search records or deduct credits
    """
    try:
        logger.info(
            f"Admin debug: Testing AITAN phone lookup for {request.country_code}{request.phone}"
        )

        # Initialize service and ensure underlying HTTP client is cleaned up
        async with AITANService() as service:
            # Measure execution time
            start_time = time.time()

            # Call service
            result = await service.search_phone(
                request.country_code, request.phone, "phone-lookup"
            )
            execution_time = (
                time.time() - start_time
            ) * 1000  # Convert to milliseconds

            # Build response
            is_success = (
                not isinstance(result, Exception)
                and isinstance(result, dict)
                and not result.get("error")
            )

            # Extract raw response from service result (strip from data to avoid duplication)
            raw_response = None
            if request.include_raw_response and isinstance(result, dict):
                raw_response = result.get("_raw_response")
            data_clean = (
                _strip_raw_from_data(result) if isinstance(result, dict) else None
            )

            response_data = ServiceTestResponse(
                service_name="aitan-phone",
                success=is_success,
                execution_time_ms=round(execution_time, 2),
                found=result.get("found") if isinstance(result, dict) else None,
                data=data_clean,
                error=(
                    str(result)
                    if isinstance(result, Exception)
                    else result.get("error")
                ),
                raw_response=raw_response,
            )

        logger.info(
            f"Admin debug: AITAN phone lookup completed in {execution_time:.2f}ms"
        )

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="AITAN phone lookup tested successfully",
        )

    except Exception as e:
        logger.error("Admin debug: AITAN phone lookup failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service test failed: {str(e)}"
        ) from e


@router.get("/phone/health", response_model=SuccessResponse[dict[str, Any]])
async def check_aitan_phone_health(
    test_phone: str = Query(
        "234567890", description="Test phone number (without country code)"
    ),
):
    """
    Quick health check for AITAN phone lookup service using a test phone number.
    Returns basic connectivity and response time information.
    """
    try:
        async with AITANService() as service:
            start_time = time.time()
            result = await service.search_phone("+1", test_phone, "phone-lookup")
            execution_time = (time.time() - start_time) * 1000

            is_healthy = (
                isinstance(result, dict)
                and not result.get("error")
                and not isinstance(result, Exception)
            )

        return SuccessResponse[dict[str, Any]](
            data={
                "service": "aitan-phone",
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time_ms": round(execution_time, 2),
                "has_error": bool(
                    result.get("error") if isinstance(result, dict) else False
                ),
            },
            success=True,
            message="Health check completed for AITAN phone lookup",
        )

    except Exception as e:
        logger.error(
            "Admin debug: Health check failed for AITAN phone lookup", exc_info=True
        )
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "aitan-phone",
                "status": "unhealthy",
                "error": str(e),
            },
            success=False,
            message="Health check failed for AITAN phone lookup",
        )


# Vehicle Lookup Endpoints
@router.post("/vehicle", response_model=SuccessResponse[ServiceTestResponse])
async def test_aitan_vehicle_lookup(request: AITANVehicleLookupRequest):
    """
    Test AITAN vehicle lookup service (all methods in parallel).

    This endpoint:
    - Bypasses orchestration and database
    - Calls all vehicle lookup methods in parallel
    - Returns detailed debugging information
    - Does NOT create search records or deduct credits
    """
    if not request.vehicle_number:
        raise HTTPException(
            status_code=400, detail="vehicle_number is required for vehicle lookup"
        )

    try:
        logger.info(
            f"Admin debug: Testing AITAN vehicle lookup for {request.vehicle_number}"
        )

        # Initialize service and ensure underlying HTTP client is cleaned up
        async with AITANService() as service:
            # Measure execution time
            start_time = time.time()

            # Call service (searches all vehicle lookup methods)
            result = await service.search_vehicle(
                request.vehicle_number, "vehicle-lookup", request.chassis_number
            )
            execution_time = (
                time.time() - start_time
            ) * 1000  # Convert to milliseconds

            # Build response
            is_success = (
                not isinstance(result, Exception)
                and isinstance(result, dict)
                and not result.get("error")
            )

            # Extract raw response from service result (strip from data to avoid duplication)
            raw_response = None
            if request.include_raw_response and isinstance(result, dict):
                raw_response = result.get("_raw_response")
            data_clean = (
                _strip_raw_from_data(result) if isinstance(result, dict) else None
            )

            response_data = ServiceTestResponse(
                service_name="aitan-vehicle",
                success=is_success,
                execution_time_ms=round(execution_time, 2),
                found=result.get("found") if isinstance(result, dict) else None,
                data=data_clean,
                error=(
                    str(result)
                    if isinstance(result, Exception)
                    else result.get("error")
                ),
                raw_response=raw_response,
            )

        logger.info(
            f"Admin debug: AITAN vehicle lookup completed in {execution_time:.2f}ms"
        )

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="AITAN vehicle lookup tested successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin debug: AITAN vehicle lookup failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service test failed: {str(e)}"
        ) from e


@router.post("/vehicle/rc-advance", response_model=SuccessResponse[ServiceTestResponse])
async def test_aitan_rc_advance(request: AITANVehicleLookupRequest):
    """Test AITAN RC advance lookup only"""
    if not request.vehicle_number:
        raise HTTPException(
            status_code=400, detail="vehicle_number is required for RC advance lookup"
        )

    try:
        async with AITANService() as service:
            start_time = time.time()
            result = await service._rc_advance(request.vehicle_number)
            execution_time = (time.time() - start_time) * 1000

            is_success = isinstance(result, dict) and not result.get("error")

            raw_response = None
            if request.include_raw_response and isinstance(result, dict):
                raw_response = result.get("_raw_response")
            data_clean = (
                _strip_raw_from_data(result) if isinstance(result, dict) else None
            )

            response_data = ServiceTestResponse(
                service_name="aitan-rc-advance",
                success=is_success,
                execution_time_ms=round(execution_time, 2),
                found=result.get("found") if isinstance(result, dict) else None,
                data=data_clean,
                error=result.get("error") if isinstance(result, dict) else None,
                raw_response=raw_response,
            )

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="AITAN RC advance tested successfully",
        )

    except Exception as e:
        logger.error("Admin debug: AITAN RC advance failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service test failed: {str(e)}"
        ) from e


@router.post(
    "/vehicle/challan-advance", response_model=SuccessResponse[ServiceTestResponse]
)
async def test_aitan_challan_advance(request: AITANVehicleLookupRequest):
    """Test AITAN challan advance lookup only"""
    if not request.vehicle_number:
        raise HTTPException(
            status_code=400,
            detail="vehicle_number is required for challan advance lookup",
        )

    try:
        async with AITANService() as service:
            start_time = time.time()
            result = await service._challan_advance(request.vehicle_number)
            execution_time = (time.time() - start_time) * 1000

            is_success = isinstance(result, dict) and not result.get("error")

            raw_response = None
            if request.include_raw_response and isinstance(result, dict):
                raw_response = result.get("_raw_response")
            data_clean = (
                _strip_raw_from_data(result) if isinstance(result, dict) else None
            )

            response_data = ServiceTestResponse(
                service_name="aitan-challan-advance",
                success=is_success,
                execution_time_ms=round(execution_time, 2),
                found=result.get("found") if isinstance(result, dict) else None,
                data=data_clean,
                error=result.get("error") if isinstance(result, dict) else None,
                raw_response=raw_response,
            )

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="AITAN challan advance tested successfully",
        )

    except Exception as e:
        logger.error("Admin debug: AITAN challan advance failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service test failed: {str(e)}"
        ) from e


@router.post(
    "/vehicle/chassis-to-rc", response_model=SuccessResponse[ServiceTestResponse]
)
async def test_aitan_chassis_to_rc(request: AITANVehicleLookupRequest):
    """Test AITAN chassis to RC lookup only"""
    chassis = request.chassis_number or request.vehicle_number
    if not chassis:
        raise HTTPException(
            status_code=400,
            detail="chassis_number or vehicle_number is required for chassis to RC lookup",
        )

    try:
        async with AITANService() as service:
            start_time = time.time()
            result = await service._chassis_to_rc(chassis)
            execution_time = (time.time() - start_time) * 1000

            is_success = isinstance(result, dict) and not result.get("error")

            raw_response = None
            if request.include_raw_response and isinstance(result, dict):
                raw_response = result.get("_raw_response")
            data_clean = (
                _strip_raw_from_data(result) if isinstance(result, dict) else None
            )

            response_data = ServiceTestResponse(
                service_name="aitan-chassis-to-rc",
                success=is_success,
                execution_time_ms=round(execution_time, 2),
                found=result.get("found") if isinstance(result, dict) else None,
                data=data_clean,
                error=result.get("error") if isinstance(result, dict) else None,
                raw_response=raw_response,
            )

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="AITAN chassis to RC tested successfully",
        )

    except Exception as e:
        logger.error("Admin debug: AITAN chassis to RC failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service test failed: {str(e)}"
        ) from e


@router.post(
    "/vehicle/fasttag-history", response_model=SuccessResponse[ServiceTestResponse]
)
async def test_aitan_fasttag_history(request: AITANVehicleLookupRequest):
    """Test AITAN FastTag history lookup only"""
    if not request.vehicle_number:
        raise HTTPException(
            status_code=400,
            detail="vehicle_number is required for FastTag history lookup",
        )

    try:
        async with AITANService() as service:
            start_time = time.time()
            result = await service._mobile_to_fasttag_history(request.vehicle_number)
            execution_time = (time.time() - start_time) * 1000

            is_success = isinstance(result, dict) and not result.get("error")

            raw_response = None
            if request.include_raw_response and isinstance(result, dict):
                raw_response = result.get("_raw_response")
            data_clean = (
                _strip_raw_from_data(result) if isinstance(result, dict) else None
            )

            response_data = ServiceTestResponse(
                service_name="aitan-fasttag-history",
                success=is_success,
                execution_time_ms=round(execution_time, 2),
                found=result.get("found") if isinstance(result, dict) else None,
                data=data_clean,
                error=result.get("error") if isinstance(result, dict) else None,
                raw_response=raw_response,
            )

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="AITAN FastTag history tested successfully",
        )

    except Exception as e:
        logger.error("Admin debug: AITAN FastTag history failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service test failed: {str(e)}"
        ) from e


@router.get("/vehicle/health", response_model=SuccessResponse[dict[str, Any]])
async def check_aitan_vehicle_health(
    test_vehicle: str = Query("MH12AB1234", description="Test vehicle number"),
):
    """
    Quick health check for AITAN vehicle lookup service using a test vehicle number.
    Returns basic connectivity and response time information.
    """
    try:
        async with AITANService() as service:
            start_time = time.time()
            result = await service.search_vehicle(test_vehicle, "vehicle-lookup")
            execution_time = (time.time() - start_time) * 1000

            is_healthy = (
                isinstance(result, dict)
                and not result.get("error")
                and not isinstance(result, Exception)
            )

        return SuccessResponse[dict[str, Any]](
            data={
                "service": "aitan-vehicle",
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time_ms": round(execution_time, 2),
                "has_error": bool(
                    result.get("error") if isinstance(result, dict) else False
                ),
            },
            success=True,
            message="Health check completed for AITAN vehicle lookup",
        )

    except Exception as e:
        logger.error(
            "Admin debug: Health check failed for AITAN vehicle lookup", exc_info=True
        )
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "aitan-vehicle",
                "status": "unhealthy",
                "error": str(e),
            },
            success=False,
            message="Health check failed for AITAN vehicle lookup",
        )
