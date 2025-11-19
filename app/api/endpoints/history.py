from __future__ import annotations

import logging

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_dependencies import get_current_user_optional
from app.models.user import User
from app.schemas.history import (
    HistorySchema,
)
from app.schemas.response import SuccessResponse
from app.services.history_service import HistoryService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{history_id}", response_model=SuccessResponse[HistorySchema])
async def get_history(
    history_id: str,
    current_user: User | None = Depends(get_current_user_optional),
):
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

    # Optionally enforce user access if current_user is used
    if current_user and history.userId and str(history.userId) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden")

    payload: HistorySchema = HistorySchema(
        id=str(history.id),
        userId=str(history.userId) if history.userId else None,
        queryType=history.queryType,
        queryInput=history.queryInput,
        status=history.status,
        results=[r.model_dump() for r in history.results],
        metadata=history.metadata.model_dump(),
        createdAt=history.createdAt,
        updatedAt=history.updatedAt,
    )

    return SuccessResponse[HistorySchema](
        success=True, message="History retrieved", data=payload
    )


@router.get("/", response_model=SuccessResponse[list[HistorySchema]])
async def list_histories(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User | None = Depends(get_current_user_optional),
):
    if not current_user:
        # If you want to allow unauthenticated listing, adjust accordingly
        raise HTTPException(status_code=401, detail="Authentication required")

    service = HistoryService()
    items, total = await service.get_user_histories(
        current_user.id, page=page, size=size
    )

    payload = [
        HistorySchema(
            id=str(h.id),
            userId=str(h.userId) if h.userId else None,
            queryType=h.queryType,
            queryInput=h.queryInput,
            status=h.status,
            results=[r.model_dump() for r in h.results],
            metadata=h.metadata.model_dump(),
            createdAt=h.createdAt,
            updatedAt=h.updatedAt,
        )
        for h in items
    ]

    return SuccessResponse[list[HistorySchema]](
        success=True,
        message="Histories retrieved",
        data=payload,
    )
