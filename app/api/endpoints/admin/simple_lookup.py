"""
Admin Debug Endpoints for Simple Lookups (IP, IMEI, Virtual Number, Virtual Email)

This module provides admin-only endpoints for debugging and testing
the new simple lookup services without going through full orchestration.

Endpoints:
- POST /admin/debug/ip-lookup - Test IP lookup (VPNAPI.io)
- POST /admin/debug/imei-lookup - Test IMEI lookup (Kelpom RapidAPI)
- POST /admin/debug/virtual-number - Test virtual number check (NumCheckr)
- POST /admin/debug/virtual-email - Test virtual email check (Email Intelligence)
- GET /admin/debug/ip-lookup/health - Health check for IP lookup
- GET /admin/debug/imei-lookup/health - Health check for IMEI lookup
- GET /admin/debug/virtual-number/health - Health check for virtual number
- GET /admin/debug/virtual-email/health - Health check for virtual email

Note: Bank and Verify ID (PAN, DL, Voter) use Befisc - see /admin/debug/befisc/
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas.admin import (
    IMEILookupDebugRequest,
    IPLookupDebugRequest,
    ServiceTestResponse,
    VirtualEmailLookupDebugRequest,
    VirtualNumberLookupDebugRequest,
)
from app.schemas.response import SuccessResponse
from app.services.integrations.imei_lookup.kelpom_service import KelpomIMEIService
from app.services.integrations.ip_lookup.vpnapi_service import VPNAPIService
from app.services.integrations.virtual_email.email_intelligence_service import (
    EmailIntelligenceService,
)
from app.services.integrations.virtual_number.numcheckr_service import NumCheckrService

router = APIRouter()
logger = logging.getLogger(__name__)


def _strip_raw_from_data(data: Any) -> Any:
    """Recursively remove _raw_response from data."""
    if isinstance(data, dict):
        return {
            k: _strip_raw_from_data(v)
            for k, v in data.items()
            if k not in ("_raw_response", "_raw_data")
        }
    if isinstance(data, list):
        return [_strip_raw_from_data(item) for item in data]
    return data


def _build_test_response(
    result: dict[str, Any],
    service_name: str,
    execution_time: float,
    include_raw: bool,
) -> ServiceTestResponse:
    """Build ServiceTestResponse from service result."""
    is_success = isinstance(result, dict) and not result.get("error")
    raw_response = (
        result.get("_raw_response")
        if include_raw and isinstance(result, dict)
        else None
    )
    data_clean = _strip_raw_from_data(result) if isinstance(result, dict) else None
    return ServiceTestResponse(
        service_name=service_name,
        success=is_success,
        execution_time_ms=round(execution_time, 2),
        found=result.get("found") if isinstance(result, dict) else None,
        data=data_clean,
        error=result.get("error") if isinstance(result, dict) else None,
        raw_response=raw_response,
    )


@router.post("/ip-lookup", response_model=SuccessResponse[ServiceTestResponse])
async def test_ip_lookup(request: IPLookupDebugRequest):
    """Test IP lookup service (VPNAPI.io). Bypasses orchestration and database."""
    try:
        start_time = time.time()
        result = await VPNAPIService().search_ip(request.ip)
        execution_time = (time.time() - start_time) * 1000
        response_data = _build_test_response(
            result, "ip-lookup-vpnapi", execution_time, request.include_raw_response
        )
        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="IP lookup tested successfully",
        )
    except Exception as e:
        logger.error("Admin debug: IP lookup failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"IP lookup failed: {str(e)}"
        ) from e


@router.get("/ip-lookup/health", response_model=SuccessResponse[dict[str, Any]])
async def check_ip_lookup_health(
    test_ip: str = Query("8.8.8.8", description="Test IP address"),
):
    """Quick health check for IP lookup."""
    try:
        start_time = time.time()
        result = await VPNAPIService().search_ip(test_ip)
        execution_time = (time.time() - start_time) * 1000
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "ip-lookup-vpnapi",
                "status": "healthy" if not result.get("error") else "unhealthy",
                "response_time_ms": round(execution_time, 2),
            },
            success=True,
            message="IP lookup health check completed",
        )
    except Exception as e:
        logger.error("Admin debug: IP lookup health check failed", exc_info=True)
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "ip-lookup-vpnapi",
                "status": "unhealthy",
                "error": str(e),
            },
            success=False,
            message="Health check failed",
        )


@router.post("/imei-lookup", response_model=SuccessResponse[ServiceTestResponse])
async def test_imei_lookup(request: IMEILookupDebugRequest):
    """Test IMEI lookup service (Kelpom RapidAPI). Bypasses orchestration and database."""
    try:
        start_time = time.time()
        result = await KelpomIMEIService().search_imei(request.imei)
        execution_time = (time.time() - start_time) * 1000
        response_data = _build_test_response(
            result, "imei-lookup-kelpom", execution_time, request.include_raw_response
        )
        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="IMEI lookup tested successfully",
        )
    except Exception as e:
        logger.error("Admin debug: IMEI lookup failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"IMEI lookup failed: {str(e)}"
        ) from e


@router.get("/imei-lookup/health", response_model=SuccessResponse[dict[str, Any]])
async def check_imei_lookup_health(
    test_imei: str = Query("354505080001234", description="Test IMEI (15 digits)"),
):
    """Quick health check for IMEI lookup."""
    try:
        start_time = time.time()
        result = await KelpomIMEIService().search_imei(test_imei)
        execution_time = (time.time() - start_time) * 1000
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "imei-lookup-kelpom",
                "status": "healthy" if not result.get("error") else "unhealthy",
                "response_time_ms": round(execution_time, 2),
            },
            success=True,
            message="IMEI lookup health check completed",
        )
    except Exception as e:
        logger.error("Admin debug: IMEI lookup health check failed", exc_info=True)
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "imei-lookup-kelpom",
                "status": "unhealthy",
                "error": str(e),
            },
            success=False,
            message="Health check failed",
        )


@router.post("/virtual-number", response_model=SuccessResponse[ServiceTestResponse])
async def test_virtual_number(request: VirtualNumberLookupDebugRequest):
    """Test virtual number check (NumCheckr). Bypasses orchestration and database."""
    try:
        start_time = time.time()
        result = await NumCheckrService().check_number(
            request.phone_number, request.country_code
        )
        execution_time = (time.time() - start_time) * 1000
        response_data = _build_test_response(
            result,
            "virtual-number-numcheckr",
            execution_time,
            request.include_raw_response,
        )
        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="Virtual number check tested successfully",
        )
    except Exception as e:
        logger.error("Admin debug: Virtual number check failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Virtual number check failed: {str(e)}"
        ) from e


@router.get("/virtual-number/health", response_model=SuccessResponse[dict[str, Any]])
async def check_virtual_number_health(
    test_phone: str = Query("9997260627", description="Test phone number"),
):
    """Quick health check for virtual number."""
    try:
        start_time = time.time()
        result = await NumCheckrService().check_number(test_phone, "+91")
        execution_time = (time.time() - start_time) * 1000
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "virtual-number-numcheckr",
                "status": "healthy" if not result.get("error") else "unhealthy",
                "response_time_ms": round(execution_time, 2),
            },
            success=True,
            message="Virtual number health check completed",
        )
    except Exception as e:
        logger.error("Admin debug: Virtual number health check failed", exc_info=True)
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "virtual-number-numcheckr",
                "status": "unhealthy",
                "error": str(e),
            },
            success=False,
            message="Health check failed",
        )


@router.post("/virtual-email", response_model=SuccessResponse[ServiceTestResponse])
async def test_virtual_email(request: VirtualEmailLookupDebugRequest):
    """Test virtual email check (Email Intelligence RapidAPI). Bypasses orchestration and database."""
    try:
        start_time = time.time()
        result = await EmailIntelligenceService().check_email(request.email)
        execution_time = (time.time() - start_time) * 1000
        response_data = _build_test_response(
            result,
            "virtual-email-intelligence",
            execution_time,
            request.include_raw_response,
        )
        return SuccessResponse[ServiceTestResponse](
            data=response_data,
            success=True,
            message="Virtual email check tested successfully",
        )
    except Exception as e:
        logger.error("Admin debug: Virtual email check failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Virtual email check failed: {str(e)}"
        ) from e


@router.get("/virtual-email/health", response_model=SuccessResponse[dict[str, Any]])
async def check_virtual_email_health(
    test_email: str = Query("test@example.com", description="Test email"),
):
    """Quick health check for virtual email."""
    try:
        start_time = time.time()
        result = await EmailIntelligenceService().check_email(test_email)
        execution_time = (time.time() - start_time) * 1000
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "virtual-email-intelligence",
                "status": "healthy" if not result.get("error") else "unhealthy",
                "response_time_ms": round(execution_time, 2),
            },
            success=True,
            message="Virtual email health check completed",
        )
    except Exception as e:
        logger.error("Admin debug: Virtual email health check failed", exc_info=True)
        return SuccessResponse[dict[str, Any]](
            data={
                "service": "virtual-email-intelligence",
                "status": "unhealthy",
                "error": str(e),
            },
            success=False,
            message="Health check failed",
        )
