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

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_dependencies import TokenData, get_current_user_token
from app.core.database import get_database
from app.models.search import SearchCreate, SearchStatus, SearchType
from app.schemas.response import SuccessResponse
from app.schemas.search import (
    EmailLookupRequest,
    PhoneLookupRequest,
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
        search_create = SearchCreate(
            user_id=user_id,
            search_type=SearchType.PHONE,
            query=f"{request.country_code}{request.phone}",
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
                "history": result["history"],
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
                "history": result["history"],
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
