from __future__ import annotations

import logging

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.database import get_database
from app.core.security import get_current_user
from app.models.search import SearchStatus, SearchType
from app.schemas.auth import TokenData
from app.schemas.search import (
    SearchCreateResponse,
    SearchListResponse,
    SearchRequest,
    SearchResponse,
    SearchStatsResponse,
    SearchSummaryResponse,
)
from app.services.result_service import ResultService
from app.services.search_orchestrator import SearchOrchestrator
from app.services.search_service import SearchService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=SearchCreateResponse)
async def create_search(
    search_request: SearchRequest,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user),
    db=Depends(get_database),
):
    """Create a new search and start execution in background"""
    try:
        search_service = SearchService(db)
        orchestrator = SearchOrchestrator(db)

        # Create search record
        from app.models.search import SearchCreate

        search_create = SearchCreate(
            search_type=search_request.search_type,
            query=search_request.query,
            user_id=ObjectId(),  # In real app, get from current_user
        )

        search = await search_service.create_search(search_create)

        # Start search execution in background
        background_tasks.add_task(orchestrator.execute_search, str(search.id))

        logger.info(f"Search created and queued: {search.id}")

        return SearchCreateResponse(
            message="Search created and queued for execution",
            search_id=str(search.id),
            status="pending",
        )

    except Exception as e:
        logger.error(f"Error creating search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create search",
        ) from e


@router.get("/{search_id}", response_model=SearchSummaryResponse)
async def get_search(
    search_id: str,
    current_user: TokenData = Depends(get_current_user),
    db=Depends(get_database),
):
    """Get search details and results"""
    try:
        orchestrator = SearchOrchestrator(db)

        # Validate search ID
        if not ObjectId.is_valid(search_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid search ID format",
            )

        summary = await orchestrator.get_search_summary(search_id)

        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Search not found"
            )

        return SearchSummaryResponse(**summary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get search",
        ) from e


@router.get("/", response_model=SearchListResponse)
async def list_searches(
    page: int = 1,
    size: int = 20,
    search_type: SearchType | None = None,
    status: SearchStatus | None = None,
    current_user: TokenData = Depends(get_current_user),
    db=Depends(get_database),
):
    """List searches with pagination and filtering"""
    try:
        search_service = SearchService(db)

        # Calculate skip
        skip = (page - 1) * size

        # Get searches
        searches = await search_service.list_searches(skip=skip, limit=size)

        # Apply filters
        if search_type:
            searches = [s for s in searches if s.search_type == search_type]
        if status:
            searches = [s for s in searches if s.status == status]

        # Convert to response format
        search_responses = [
            SearchResponse(
                id=str(search.id),
                search_type=search.search_type,
                query=search.query,
                status=search.status,
                results_count=search.results_count,
                error_message=search.error_message,
                created_at=search.created_at,
                updated_at=search.updated_at,
            )
            for search in searches
        ]

        return SearchListResponse(
            searches=search_responses, total=len(search_responses), page=page, size=size
        )

    except Exception as e:
        logger.error(f"Error listing searches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list searches",
        ) from e


@router.get("/stats/overview", response_model=SearchStatsResponse)
async def get_search_stats(
    current_user: TokenData = Depends(get_current_user), db=Depends(get_database)
):
    """Get search statistics"""
    try:
        search_service = SearchService(db)

        # Get stats by status
        status_stats = await search_service.get_search_stats()

        # Get all searches for type stats
        all_searches = await search_service.list_searches(skip=0, limit=1000)
        type_stats = {}
        for search in all_searches:
            search_type = search.search_type.value
            type_stats[search_type] = type_stats.get(search_type, 0) + 1

        return SearchStatsResponse(
            total_searches=len(all_searches),
            searches_by_status=status_stats,
            searches_by_type=type_stats,
        )

    except Exception as e:
        logger.error(f"Error getting search stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get search statistics",
        ) from e


@router.delete("/{search_id}")
async def delete_search(
    search_id: str,
    current_user: TokenData = Depends(get_current_user),
    db=Depends(get_database),
):
    """Delete a search and its results"""
    try:
        search_service = SearchService(db)
        result_service = ResultService(db)

        # Validate search ID
        if not ObjectId.is_valid(search_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid search ID format",
            )

        # Delete search
        deleted = await search_service.delete_search(search_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Search not found"
            )

        # Delete associated results
        await result_service.delete_results_by_search_id(search_id)

        logger.info(f"Search deleted: {search_id}")

        return {"message": "Search deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete search",
        ) from e
