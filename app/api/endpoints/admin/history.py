"""Admin endpoints for history management.

Provides endpoints to list and view search history across users (no auth required):
- GET /admin/debug/history - List histories (all users or by user_id) with optional searchType filter
- GET /admin/debug/history/{history_id} - Get history details by ID (bypass user check)

Allowed searchType values: phone-lookup, email-lookup, domain-lookup, vehicle-rc,
vehicle-fast-tag, vehicle-all, vehicle-chasis, username-lookup, ip-lookup, imei-lookup,
virtual-number, virtual-email, bank-account, verify-id, dark-web-leak, seeker-lookup
"""

from __future__ import annotations

import logging

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query

from app.schemas.history import (
    HISTORY_SEARCH_TYPES,
    HistoryListItemSchema,
    HistoryListResponse,
    HistorySchema,
)
from app.schemas.response import PaginationMeta, SuccessResponse
from app.services.history_service import HistoryService

router = APIRouter()
logger = logging.getLogger(__name__)

SEARCH_TYPES_DOC = ", ".join(HISTORY_SEARCH_TYPES)


@router.get("/", response_model=HistoryListResponse)
async def admin_list_histories(
    page: int = Query(1, ge=1),
    size: int = Query(
        10, ge=1, le=100, description="Number of items per page (default: 10)"
    ),
    user_id: str | None = Query(
        None,
        description="Filter by user ID. Omit to list all users' history.",
    ),
    searchType: str | None = Query(
        None,
        description=f"Filter by search type. Allowed: {SEARCH_TYPES_DOC}",
    ),
):
    """
    List search history. Optionally filter by user_id and/or searchType.
    Returns paginated metadata. Use detail endpoint for full results.
    """
    service = HistoryService()
    resolved_user_id = PydanticObjectId(user_id) if user_id else None
    items, total = await service.get_histories_admin(
        user_id=resolved_user_id,
        page=page,
        size=size,
        query_type=searchType,
    )

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


@router.get("/{history_id}", response_model=SuccessResponse[HistorySchema])
async def admin_get_history(history_id: str):
    """
    Get full history details by ID.
    """
    service = HistoryService()
    try:
        history = await service.get_history_by_id(PydanticObjectId(history_id))
    except Exception as e:
        logger.error(
            "Admin history lookup error",
            extra={"history_id": history_id, "exception": type(e).__name__},
        )
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    payload = HistorySchema(
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
