"""
Admin Debug Endpoints for Befisc Service

This module provides admin-only endpoints for debugging and testing
Befisc API service with different lookup types without going through the full
orchestration, database persistence, or billing logic.

Endpoints:
- POST /admin/debug/befisc/{lookup_type} - Test Befisc service with specific lookup type
- GET /admin/debug/befisc/{lookup_type}/health - Quick health check for a lookup type
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas.admin import BefiscLookupRequest, ServiceTestResponse
from app.schemas.response import SuccessResponse
from app.services.integrations.phone_lookup.befisc_service import BefiscService

router = APIRouter()
logger = logging.getLogger(__name__)

# Valid lookup types for Befisc
BEFISC_LOOKUP_TYPES = [
    "phone-lookup",
    "vehicle-lookup",
    "bank-lookup",
    "pan-lookup",
    "driving-license-lookup",
    "voter-id-lookup",
]


def _validate_befisc_request(request: BefiscLookupRequest) -> None:
    """Validate that required parameters are provided for the lookup type"""
    if request.lookup_type == "phone-lookup":
        if not request.country_code or not request.phone:
            raise HTTPException(
                status_code=400,
                detail="country_code and phone are required for phone-lookup",
            )
    elif request.lookup_type == "vehicle-lookup":
        if not request.vehicle_number:
            raise HTTPException(
                status_code=400,
                detail="vehicle_number is required for vehicle-lookup",
            )
    elif request.lookup_type == "bank-lookup":
        if (not request.account_no or not request.ifsc_code) and not request.upi:
            raise HTTPException(
                status_code=400,
                detail="Either (account_no and ifsc_code) or upi is required for bank-lookup",
            )
    elif request.lookup_type == "pan-lookup":
        if not request.pan:
            raise HTTPException(
                status_code=400, detail="pan is required for pan-lookup"
            )
    elif request.lookup_type == "driving-license-lookup":
        if not request.license_number or not request.dob:
            raise HTTPException(
                status_code=400,
                detail="license_number and dob are required for driving-license-lookup",
            )
    elif request.lookup_type == "voter-id-lookup" and not request.epic_number:
        raise HTTPException(
            status_code=400, detail="epic_number is required for voter-id-lookup"
        )


async def _call_befisc_service(
    service: BefiscService, request: BefiscLookupRequest
) -> dict[str, Any]:
    """Call the appropriate Befisc service method based on lookup type"""
    if request.lookup_type == "phone-lookup":
        return await service.search_phone(
            request.country_code or "",
            request.phone or "",
            "phone-lookup",
            name=request.name or "",
        )
    elif request.lookup_type == "vehicle-lookup":
        # For vehicle lookup, we need to call the individual methods
        # Since search_phone doesn't handle vehicle lookup directly,
        # we'll call the internal methods
        tasks = []
        if hasattr(service, "_rc_search_advance_v3"):
            tasks.append(service._rc_search_advance_v3(request.vehicle_number or ""))
        if hasattr(service, "_rc_search_challan_details"):
            tasks.append(
                service._rc_search_challan_details(request.vehicle_number or "")
            )
        if hasattr(service, "_rc_fastag_info"):
            tasks.append(service._rc_fastag_info(request.vehicle_number or ""))

        if not tasks:
            return {
                "found": False,
                "source": "befisc",
                "error": "No vehicle lookup methods available",
            }

        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Combine results
        combined_data = {}
        found_any = False
        raw_responses = {}

        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Befisc vehicle lookup task failed",
                    exc_info=True,
                    extra={
                        "vehicle_number": request.vehicle_number,
                        "task_index": idx,
                        "lookup_type": request.lookup_type,
                    },
                )
                continue
            if isinstance(result, dict):
                raw_responses.update(result.get("_raw_response", {}))
                if result.get("found", False):
                    found_any = True
                    data = result.get("data", {})
                    if data:
                        combined_data.update(data)

        return {
            "found": found_any,
            "source": "befisc",
            "data": combined_data if combined_data else None,
            "confidence": 0.8 if found_any else 0.0,
            "_raw_response": raw_responses,
        }
    elif request.lookup_type == "bank-lookup":
        # For bank lookup, try account/IFSC first, then UPI
        if request.account_no and request.ifsc_code:
            return await service._bank_search(request.account_no, request.ifsc_code)
        elif request.upi:
            return await service._upi_search(request.upi)
        else:
            return {
                "found": False,
                "source": "befisc",
                "error": "Either account_no/ifsc_code or upi required",
            }
    elif request.lookup_type == "pan-lookup":
        return await service._pan_search(request.pan or "")
    elif request.lookup_type == "driving-license-lookup":
        return await service._driving_license_search(
            request.license_number or "", request.dob or ""
        )
    elif request.lookup_type == "voter-id-lookup":
        return await service._voter_id_search(request.epic_number or "")
    else:
        return {
            "found": False,
            "source": "befisc",
            "error": f"Unknown lookup type: {request.lookup_type}",
        }


@router.post(
    "/befisc/{lookup_type}",
    response_model=SuccessResponse[ServiceTestResponse],
)
async def test_befisc_service(
    lookup_type: str,
    request: BefiscLookupRequest,
):
    """
    Test Befisc service with a specific lookup type.

    This endpoint:
    - Bypasses orchestration and database
    - Calls the service directly
    - Returns detailed debugging information
    - Does NOT create search records or deduct credits

    Available lookup types:
    - phone-lookup: Requires country_code and phone
    - vehicle-lookup: Requires vehicle_number
    - bank-lookup: Requires (account_no and ifsc_code) or upi
    - pan-lookup: Requires pan
    - driving-license-lookup: Requires license_number and dob (DD-MM-YYYY)
    - voter-id-lookup: Requires epic_number
    """
    lookup_type_lower = lookup_type.lower()

    if lookup_type_lower not in BEFISC_LOOKUP_TYPES:
        raise HTTPException(
            status_code=404,
            detail=f"Lookup type '{lookup_type}' not found. Available: {', '.join(BEFISC_LOOKUP_TYPES)}",
        )

    # Update request with lookup_type from path
    request.lookup_type = lookup_type_lower

    # Validate request
    _validate_befisc_request(request)

    try:
        logger.info(
            f"Admin debug: Testing Befisc {lookup_type_lower} with provided parameters"
        )

        # Initialize service
        service = BefiscService()

        # Measure execution time
        start_time = time.time()

        # Call service
        result = await _call_befisc_service(service, request)
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
            service_name=f"befisc-{lookup_type_lower}",
            success=is_success,
            execution_time_ms=round(execution_time, 2),
            found=result.get("found") if isinstance(result, dict) else None,
            data=result if isinstance(result, dict) else None,
            error=str(result) if isinstance(result, Exception) else result.get("error"),
            raw_response=raw_response,
        )

        logger.info(
            f"Admin debug: Befisc {lookup_type_lower} completed in {execution_time:.2f}ms"
        )

        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message=f"Befisc '{lookup_type}' tested successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin debug: Befisc {lookup_type_lower} failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Service test failed: {str(e)}"
        ) from e


@router.get(
    "/befisc/{lookup_type}/health",
    response_model=SuccessResponse[dict[str, Any]],
)
async def check_befisc_service_health(
    lookup_type: str,
    test_value: str = Query(
        "234567890",
        description="Test value (phone/vehicle/pan/etc based on lookup type)",
    ),
):
    """
    Quick health check for a Befisc lookup type using a test value.
    Returns basic connectivity and response time information.
    """
    lookup_type_lower = lookup_type.lower()

    if lookup_type_lower not in BEFISC_LOOKUP_TYPES:
        raise HTTPException(
            status_code=404, detail=f"Lookup type '{lookup_type}' not found"
        )

    try:
        service = BefiscService()

        # Create a minimal request for health check
        request = BefiscLookupRequest(
            lookup_type=lookup_type_lower,
            country_code="+1" if lookup_type_lower == "phone-lookup" else None,
            phone=test_value if lookup_type_lower == "phone-lookup" else None,
            vehicle_number=(
                test_value if lookup_type_lower == "vehicle-lookup" else None
            ),
            pan=test_value if lookup_type_lower == "pan-lookup" else None,
            epic_number=test_value if lookup_type_lower == "voter-id-lookup" else None,
            license_number=(
                test_value if lookup_type_lower == "driving-license-lookup" else None
            ),
            dob="01-01-1990" if lookup_type_lower == "driving-license-lookup" else None,
            account_no=test_value if lookup_type_lower == "bank-lookup" else None,
            ifsc_code="TEST0000001" if lookup_type_lower == "bank-lookup" else None,
        )

        start_time = time.time()
        result = await _call_befisc_service(service, request)
        execution_time = (time.time() - start_time) * 1000

        is_healthy = (
            isinstance(result, dict)
            and not result.get("error")
            and not isinstance(result, Exception)
        )

        return SuccessResponse[dict[str, Any]](
            data={
                "service": f"befisc-{lookup_type_lower}",
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time_ms": round(execution_time, 2),
                "has_error": bool(
                    result.get("error") if isinstance(result, dict) else False
                ),
            },
            success=True,
            message=f"Health check completed for Befisc {lookup_type}",
        )

    except Exception as e:
        logger.error(
            f"Admin debug: Health check failed for Befisc {lookup_type_lower}",
            exc_info=True,
        )
        return SuccessResponse[dict[str, Any]](
            data={
                "service": f"befisc-{lookup_type_lower}",
                "status": "unhealthy",
                "error": str(e),
            },
            success=False,
            message=f"Health check failed for Befisc {lookup_type}",
        )
