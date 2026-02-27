"""
Production-Ready Search API Endpoints

This module provides production-ready search endpoints that:
- Create search records in the database
- Execute searches using SearchOrchestrator
- Track search history and status
- Provide comprehensive search management

Endpoints:
- POST /search - Create and execute a search
- GET /search/{search_id} - Get search results by ID
- GET /searches - Get user searches with pagination
- GET /search-stats - Get search statistics
- POST /phone-lookup - Create and execute phone lookup search

Note: This file was converted from demo.py to production-ready endpoints.
The original demo functionality has been replaced with full database persistence
and proper search workflow management.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.models.search import SearchCreate, SearchStatus, SearchType
from app.schemas.response import SuccessResponse
from app.schemas.search import (
    BankLookupRequest,
    DarkWebLeakRequest,
    EmailLookupRequest,
    IMEILookupRequest,
    IPLookupRequest,
    PhoneLookupRequest,
    VehicleLookupRequest,
    VerifyIdRequest,
    VirtualEmailLookupRequest,
    VirtualNumberLookupRequest,
)
from app.services.orchestrators.search_orchestrator import SearchOrchestrator
from app.services.search_service import SearchService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search/{search_id}", response_model=SuccessResponse[dict[str, Any]])
async def get_search_results(
    search_id: str,
    db=Depends(get_database),
):
    """
    Get search results by search ID.
    Returns the complete search information including results and status.
    """
    try:
        search_service = SearchService(db)
        search = await search_service.get_search_by_id(search_id)

        if not search:
            raise HTTPException(status_code=404, detail="Search not found")

        # Get search summary using SearchOrchestrator
        search_orchestrator = SearchOrchestrator(db)
        summary = await search_orchestrator.get_search_summary(search_id)

        return SuccessResponse[dict[str, Any]](
            data=summary, success=True, message="Search results retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Search retrieval failed",
            extra={"exception": type(e).__name__, "search_id": search_id},
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/searches", response_model=SuccessResponse[dict[str, Any]])
async def get_user_searches(
    user_id: PydanticObjectId | None = Query(None, description="User ID"),
    limit: int = Query(20, ge=1, le=100, description="Number of searches to return"),
    skip: int = Query(0, ge=0, description="Number of searches to skip"),
    db=Depends(get_database),
):
    """
    Get searches for a user with pagination.
    If no user_id provided, returns system searches.
    """
    try:
        search_service = SearchService(db)

        if user_id:
            searches = await search_service.get_searches_by_user_id(
                str(user_id), limit, skip
            )
        else:
            # Get recent searches regardless of user
            searches = await search_service.get_searches_by_status(
                SearchStatus.COMPLETED, limit
            )

        formatted_searches = []
        for search in searches:
            formatted_searches.append(
                {
                    "id": str(search.id),
                    "user_id": str(search.user_id) if search.user_id else None,
                    "search_type": search.search_type.value,
                    "query": search.query,
                    "status": search.status.value,
                    "results_count": search.results_count,
                    "error_message": search.error_message,
                    "created_at": search.created_at.isoformat(),
                    "updated_at": search.updated_at.isoformat(),
                }
            )

        return SuccessResponse[dict[str, Any]](
            data={
                "searches": formatted_searches,
                "total_returned": len(formatted_searches),
                "limit": limit,
                "skip": skip,
            },
            success=True,
            message=f"Retrieved {len(formatted_searches)} searches",
        )

    except Exception as e:
        logger.error(
            "Search list retrieval failed",
            extra={
                "exception": type(e).__name__,
                "user_id": str(user_id) if user_id else None,
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/search-stats", response_model=SuccessResponse[dict[str, Any]])
async def get_search_statistics(
    db=Depends(get_database),
):
    """
    Get search statistics including counts by type and status.
    """
    try:
        search_service = SearchService(db)
        stats = await search_service.get_search_stats()

        return SuccessResponse[dict[str, Any]](
            data=stats, success=True, message="Search statistics retrieved successfully"
        )

    except Exception as e:
        logger.error(
            "Search statistics retrieval failed", extra={"exception": type(e).__name__}
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/phone-lookup", response_model=SuccessResponse[dict[str, Any]])
async def create_phone_lookup_search(
    request: PhoneLookupRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    try:
        logger.info(
            f"Phone lookup search started: {request.country_code}{request.phone}"
        )

        # Create search service and orchestrator
        search_service = SearchService(db)
        search_orchestrator = SearchOrchestrator(db)

        # Create search record for phone lookup
        # Extract user_id from authenticated token
        user_id = (
            PydanticObjectId(current_user.user_id) if current_user.user_id else None
        )

        # Encode advanced lookup flag into the query so that the search orchestrator
        # can pass it down to the phone lookup adapter/orchestrator without changing
        # the search model schema.
        base_query = f"{request.country_code}{request.phone}"
        query = f"ADV|{base_query}" if request.is_advance else base_query

        search_create = SearchCreate(
            user_id=user_id,
            search_type=SearchType.PHONE,
            query=query,
        )

        search = await search_service.create_search(search_create)
        logger.info(f"Phone search record created: {search.id}")

        # Execute the phone lookup search
        result = await search_orchestrator.execute_search(str(search.id))

        logger.info(f"Phone lookup completed: {search.id} - Status: {result['status']}")

        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "phone": f"{request.country_code}{request.phone}",
                "country_code": request.country_code,
                "status": result["status"],
                "results_count": result["results_count"],
                "failed_count": result["failed_count"],
                "error_message": result.get("error_message"),
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"Phone lookup executed successfully with {result['results_count']} successful results",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Phone lookup failed",
            extra={
                "exception": type(e).__name__,
                "phone": request.phone,
                "country_code": request.country_code,
                "user_id": current_user.user_id,
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/vehicle-lookup", response_model=SuccessResponse[dict[str, Any]])
async def create_vehicle_lookup_search(
    request: VehicleLookupRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    try:
        lookup_type = (
            "chassis" if request.lookup_type == "chasis" else request.lookup_type
        )

        if lookup_type == "chassis" and not request.chassis_number:
            raise HTTPException(
                status_code=400,
                detail="chassis_number is required for chassis lookup",
            )

        if lookup_type != "chassis" and not request.vehicle_number:
            raise HTTPException(
                status_code=400,
                detail="vehicle_number is required for this lookup type",
            )

        lookup_value = (
            request.chassis_number
            if lookup_type == "chassis"
            else request.vehicle_number
        )
        logger.info(
            "Vehicle lookup search started: %s (type=%s)",
            lookup_value,
            lookup_type,
        )

        # Create search service and orchestrator
        search_service = SearchService(db)
        search_orchestrator = SearchOrchestrator(db)

        # Extract user_id from authenticated token
        user_id = (
            PydanticObjectId(current_user.user_id) if current_user.user_id else None
        )

        # Encode vehicle lookup params into the query so we can parse it later.
        query = urlencode(
            {
                "veh": request.vehicle_number or "",
                "ch": request.chassis_number or "",
                "type": lookup_type,
            }
        )

        search_type_map = {
            "rc": SearchType.VEHICLE_RC,
            "fast-tag": SearchType.VEHICLE_FAST_TAG,
            "all": SearchType.VEHICLE_ALL,
            "chassis": SearchType.VEHICLE_CHASIS,
        }
        search_type = search_type_map.get(lookup_type, SearchType.VEHICLE_ALL)

        search_create = SearchCreate(
            user_id=user_id,
            search_type=search_type,
            query=query,
        )

        search = await search_service.create_search(search_create)
        logger.info(f"Vehicle search record created: {search.id}")

        # Execute the vehicle lookup search
        result = await search_orchestrator.execute_search(str(search.id))

        logger.info(
            f"Vehicle lookup completed: {search.id} - Status: {result['status']}"
        )

        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "vehicle_number": request.vehicle_number,
                "chassis_number": request.chassis_number,
                "lookup_type": lookup_type,
                "status": result["status"],
                "results_count": result["results_count"],
                "failed_count": result["failed_count"],
                "error_message": result.get("error_message"),
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=(
                "Vehicle lookup executed successfully with "
                f"{result['results_count']} successful results"
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Vehicle lookup failed",
            extra={
                "exception": type(e).__name__,
                "vehicle_number": request.vehicle_number,
                "user_id": current_user.user_id,
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/email-lookup", response_model=SuccessResponse[dict[str, Any]])
async def create_email_lookup_search(
    request: EmailLookupRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    try:
        logger.info(f"Email lookup search started: {request.email}")

        # Create search service and orchestrator
        search_service = SearchService(db)
        search_orchestrator = SearchOrchestrator(db)

        # Create search record for email lookup
        # Extract user_id from authenticated token
        user_id = (
            PydanticObjectId(current_user.user_id) if current_user.user_id else None
        )
        search_create = SearchCreate(
            user_id=user_id,
            search_type=SearchType.EMAIL,
            query=request.email,
        )

        search = await search_service.create_search(search_create)
        logger.info(f"Email search record created: {search.id}")

        # Execute the email lookup search
        result = await search_orchestrator.execute_search(str(search.id))

        logger.info(f"Email lookup completed: {search.id} - Status: {result['status']}")

        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "email": request.email,
                "status": result["status"],
                "results_count": result["results_count"],
                "failed_count": result["failed_count"],
                "error_message": result.get("error_message"),
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"Email lookup executed successfully with {result['results_count']} successful results",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Email lookup failed",
            extra={
                "exception": type(e).__name__,
                "email": request.email,
                "user_id": current_user.user_id,
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/bank-lookup", response_model=SuccessResponse[dict[str, Any]])
async def create_bank_lookup_search(
    request: BankLookupRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Bank account lookup by account+IFSC or UPI."""
    if (request.account_no and request.ifsc_code) or request.upi:
        pass
    else:
        raise HTTPException(
            status_code=400,
            detail="Either (account_no and ifsc_code) or upi is required",
        )
    try:
        query = (
            f"acc={request.account_no or ''}|ifsc={request.ifsc_code or ''}"
            if request.account_no and request.ifsc_code
            else f"upi={request.upi or ''}"
        )
        search_create = SearchCreate(
            user_id=(
                PydanticObjectId(current_user.user_id) if current_user.user_id else None
            ),
            search_type=SearchType.BANK_ACCOUNT,
            query=query,
        )
        search = await SearchService(db).create_search(search_create)
        result = await SearchOrchestrator(db).execute_search(str(search.id))
        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "status": result["status"],
                "results_count": result["results_count"],
                "failed_count": result["failed_count"],
                "error_message": result.get("error_message"),
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"Bank lookup executed with {result['results_count']} results",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Bank lookup failed", extra={"exception": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/verify-id", response_model=SuccessResponse[dict[str, Any]])
async def create_verify_id_search(
    request: VerifyIdRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Verify ID (PAN, DL, Voter ID). DL requires dob (DD-MM-YYYY)."""
    if request.id_type == "dl" and not request.dob:
        raise HTTPException(
            status_code=400,
            detail="dob (DD-MM-YYYY) is required for driving license",
        )
    try:
        query = f"type={request.id_type}|value={request.value}"
        if request.dob:
            query += f"|dob={request.dob}"
        search_create = SearchCreate(
            user_id=(
                PydanticObjectId(current_user.user_id) if current_user.user_id else None
            ),
            search_type=SearchType.VERIFY_ID,
            query=query,
        )
        search = await SearchService(db).create_search(search_create)
        result = await SearchOrchestrator(db).execute_search(str(search.id))
        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "id_type": request.id_type,
                "status": result["status"],
                "results_count": result["results_count"],
                "failed_count": result["failed_count"],
                "error_message": result.get("error_message"),
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"Verify ID executed with {result['results_count']} results",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Verify ID failed", extra={"exception": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/ip-lookup", response_model=SuccessResponse[dict[str, Any]])
async def create_ip_lookup_search(
    request: IPLookupRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    try:
        search_create = SearchCreate(
            user_id=(
                PydanticObjectId(current_user.user_id) if current_user.user_id else None
            ),
            search_type=SearchType.IP_LOOKUP,
            query=request.ip,
        )
        search = await SearchService(db).create_search(search_create)
        result = await SearchOrchestrator(db).execute_search(str(search.id))
        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "ip": request.ip,
                "status": result["status"],
                "results_count": result["results_count"],
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"IP lookup executed with {result['results_count']} results",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("IP lookup failed", extra={"exception": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/imei-lookup", response_model=SuccessResponse[dict[str, Any]])
async def create_imei_lookup_search(
    request: IMEILookupRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    try:
        search_create = SearchCreate(
            user_id=(
                PydanticObjectId(current_user.user_id) if current_user.user_id else None
            ),
            search_type=SearchType.IMEI_LOOKUP,
            query=request.imei,
        )
        search = await SearchService(db).create_search(search_create)
        result = await SearchOrchestrator(db).execute_search(str(search.id))
        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "imei": request.imei,
                "status": result["status"],
                "results_count": result["results_count"],
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"IMEI lookup executed with {result['results_count']} results",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("IMEI lookup failed", extra={"exception": type(e).__name__})
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/virtual-number", response_model=SuccessResponse[dict[str, Any]])
async def create_virtual_number_search(
    request: VirtualNumberLookupRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    try:
        query = f"ph={request.phone_number}|cc={request.country_code}"
        search_create = SearchCreate(
            user_id=(
                PydanticObjectId(current_user.user_id) if current_user.user_id else None
            ),
            search_type=SearchType.VIRTUAL_NUMBER,
            query=query,
        )
        search = await SearchService(db).create_search(search_create)
        result = await SearchOrchestrator(db).execute_search(str(search.id))
        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "phone_number": request.phone_number,
                "status": result["status"],
                "results_count": result["results_count"],
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"Virtual number check executed with {result['results_count']} results",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Virtual number check failed", extra={"exception": type(e).__name__}
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/dark-web-leak", response_model=SuccessResponse[dict[str, Any]])
async def create_dark_web_leak_search(
    request: DarkWebLeakRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    """Dark web leaked data search by email, mobile, username, or keyword."""
    try:
        logger.info(
            "Dark web leak search started: type=%s, value=%s",
            request.query_type,
            (
                request.query_data[:20] + "..."
                if len(request.query_data) > 20
                else request.query_data
            ),
        )

        query = f"type={request.query_type}|value={request.query_data}|cc={request.country_code}"

        search_create = SearchCreate(
            user_id=(
                PydanticObjectId(current_user.user_id) if current_user.user_id else None
            ),
            search_type=SearchType.DARK_WEB_LEAK,
            query=query,
        )
        search = await SearchService(db).create_search(search_create)
        result = await SearchOrchestrator(db).execute_search(str(search.id))

        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "query_type": request.query_type,
                "query_data": request.query_data,
                "status": result["status"],
                "results_count": result["results_count"],
                "failed_count": result["failed_count"],
                "error_message": result.get("error_message"),
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"Dark web leak search executed with {result['results_count']} results",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Dark web leak search failed",
            extra={
                "exception": type(e).__name__,
                "query_type": request.query_type,
                "user_id": current_user.user_id,
            },
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/virtual-email", response_model=SuccessResponse[dict[str, Any]])
async def create_virtual_email_search(
    request: VirtualEmailLookupRequest,
    current_user: TokenData = Depends(get_current_user_token),
    db=Depends(get_database),
):
    try:
        search_create = SearchCreate(
            user_id=(
                PydanticObjectId(current_user.user_id) if current_user.user_id else None
            ),
            search_type=SearchType.VIRTUAL_EMAIL,
            query=request.email,
        )
        search = await SearchService(db).create_search(search_create)
        result = await SearchOrchestrator(db).execute_search(str(search.id))
        return SuccessResponse[dict[str, Any]](
            data={
                "search_id": str(search.id),
                "email": request.email,
                "status": result["status"],
                "results_count": result["results_count"],
                "results": result["results"],
                "created_at": search.created_at.isoformat(),
                "updated_at": search.updated_at.isoformat(),
            },
            success=True,
            message=f"Virtual email check executed with {result['results_count']} results",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Virtual email check failed", extra={"exception": type(e).__name__}
        )
        raise HTTPException(status_code=500, detail=str(e)) from e
