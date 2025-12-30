from __future__ import annotations

import logging

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_dependencies import (
    TokenData,
    get_current_user_optional,
    get_current_user_token,
)
from app.schemas.history import (
    HistoryListItemSchema,
    HistoryListResponse,
    HistorySchema,
)
from app.schemas.response import PaginationMeta, SuccessResponse
from app.services.history_service import HistoryService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{history_id}", response_model=SuccessResponse[HistorySchema])
async def get_history(
    history_id: str,
    current_user: TokenData | None = Depends(get_current_user_optional),
):
    """
    Get full history details by ID including flattenedResults.
    Use this endpoint when clicking on a history item from the list.
    """
    # Require authentication for accessing history
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = HistoryService()
    try:
        history = await service.get_history_by_id(PydanticObjectId(history_id))
    except Exception as e:
        logger.error(
            "History lookup error",
            extra={"history_id": history_id, "exception": type(e).__name__},
        )
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    # Enforce user access - users can only access their own history
    if history.userId and str(history.userId) != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    payload: HistorySchema = HistorySchema(
        id=str(history.id),
        userId=str(history.userId) if history.userId else None,
        queryType=history.queryType,
        queryInput=history.queryInput,
        status=history.status,
        flattenedResults=history.flattenedResults or [],
        metadata=history.metadata.model_dump(),
        createdAt=history.createdAt,
        updatedAt=history.updatedAt,
    )

    return SuccessResponse[HistorySchema](
        success=True, message="History retrieved", data=payload
    )


@router.get("/", response_model=HistoryListResponse)
async def list_histories(
    page: int = Query(1, ge=1),
    size: int = Query(
        10, ge=1, le=100, description="Number of items per page (default: 10)"
    ),
    current_user: TokenData | None = Depends(get_current_user_optional),
):
    """
    Get paginated list of user's search history with metadata only.
    Returns only: id, queryType, queryInput, status, createdAt
    Use the detail endpoint to get full information including flattenedResults.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    service = HistoryService()
    items, total = await service.get_user_histories(
        PydanticObjectId(current_user.user_id), page=page, size=size
    )

    # Return only metadata for list view
    payload = [
        HistoryListItemSchema(
            id=str(h.id),
            queryType=h.queryType,
            queryInput=h.queryInput,
            status=h.status,
            createdAt=h.createdAt,
        )
        for h in items
    ]

    # Calculate pagination metadata
    pages = (total + size - 1) // size if total > 0 else 0
    pagination = PaginationMeta(
        page=page,
        size=size,
        total=total,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )

    return HistoryListResponse(
        success=True,
        message=f"Retrieved {len(payload)} history items",
        data=payload,
        pagination=pagination,
    )


@router.delete("/", response_model=SuccessResponse[dict])
async def delete_all_history(
    current_user: TokenData = Depends(get_current_user_token),
):
    """
    Delete all history data for the current authenticated user.
    Only history data is deleted; user, credits, and credits_transaction data remain untouched.
    """
    service = HistoryService()
    try:
        deleted_count = await service.delete_all_user_history(
            PydanticObjectId(current_user.user_id)
        )
        logger.info(
            "All user history deleted via API",
            extra={
                "user_id": current_user.user_id,
                "deleted_count": deleted_count,
            },
        )
        return SuccessResponse[dict](
            success=True,
            message=f"Successfully deleted {deleted_count} history record(s)",
            data={"deleted_count": deleted_count},
        )
    except Exception as e:
        logger.error(
            "Error deleting all user history",
            extra={
                "user_id": current_user.user_id,
                "exception": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete history: {str(e)}"
        ) from e
