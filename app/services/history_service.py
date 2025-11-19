from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId

from app.models.history import History, HistorySourceResult

logger = logging.getLogger(__name__)


class HistoryService:
    async def create_history(
        self,
        *,
        user_id: PydanticObjectId | None,
        query_type: str,
        query_input: dict[str, Any] | str,
    ) -> History:
        history = History(
            userId=user_id,
            queryType=query_type,
            queryInput=query_input,
            status="IN_PROGRESS",
        )
        await history.insert()
        logger.info(
            "History created",
            extra={"history_id": str(history.id), "query_type": query_type},
        )
        return history

    async def add_result(
        self,
        history_id: PydanticObjectId,
        result: HistorySourceResult,
    ) -> History:
        history = await History.get(history_id)
        if not history:
            raise ValueError("History not found")

        history.results.append(result)
        # update metadata counts
        meta = history.metadata
        meta.totalSources += 1 if meta.totalSources < len(history.results) else 0
        if result.success:
            meta.successfulSources += 1
        else:
            meta.failedSources += 1
        history.updatedAt = datetime.now(UTC)
        await history.save()
        logger.info(
            "History result added",
            extra={
                "history_id": str(history.id),
                "source": result.source,
                "success": result.success,
            },
        )
        return history

    async def finalize_history(
        self,
        history_id: PydanticObjectId,
        *,
        total_sources: int,
    ) -> History:
        history = await History.get(history_id)
        if not history:
            raise ValueError("History not found")

        meta = history.metadata
        meta.totalSources = total_sources
        meta.completedAt = datetime.now(UTC)
        if meta.startedAt:
            # Ensure both datetimes are timezone-aware before subtraction
            started_at = meta.startedAt
            if started_at.tzinfo is None:
                # If naive, assume it's UTC
                started_at = started_at.replace(tzinfo=UTC)
            completed_at = meta.completedAt
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=UTC)
            meta.durationMs = int((completed_at - started_at).total_seconds() * 1000)

        if meta.successfulSources == 0 and meta.failedSources > 0:
            history.status = "FAILED"
        elif meta.failedSources > 0:
            history.status = "PARTIAL"
        else:
            history.status = "COMPLETED"

        history.updatedAt = datetime.now(UTC)
        await history.save()
        logger.info(
            "History finalized",
            extra={
                "history_id": str(history.id),
                "status": history.status,
                "success_count": meta.successfulSources,
                "failed_count": meta.failedSources,
            },
        )
        return history

    async def get_history_by_id(self, history_id: PydanticObjectId) -> History | None:
        return await History.get(history_id)

    async def get_user_histories(
        self,
        user_id: PydanticObjectId,
        *,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[History], int]:
        skip = max(0, (page - 1) * size)
        cursor = History.find(History.userId == user_id).sort("-createdAt")
        total = await cursor.count()
        items = await cursor.skip(skip).limit(size).to_list()
        return items, total
