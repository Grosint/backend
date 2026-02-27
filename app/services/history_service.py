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

        # Decrypt data before modifying
        history.decrypt_sensitive_data()

        history.results.append(result)
        # update metadata counts
        meta = history.metadata
        meta.totalSources = len(history.results)
        if result.success:
            meta.successfulSources += 1
        else:
            meta.failedSources += 1
        history.updatedAt = datetime.now(UTC)
        # Use replace() to ensure encryption hook is triggered
        # Encryption happens automatically in @before_event hook
        await history.replace()
        logger.info(
            "History result added",
            extra={
                "history_id": str(history.id),
                "source": result.source,
                "success": result.success,
            },
        )
        return history

    async def store_flattened_results(
        self,
        history_id: PydanticObjectId,
        flattened_results: list[dict[str, Any]],
    ) -> History:
        """Store flattened results in history for easy UI rendering"""
        history = await History.get(history_id)
        if not history:
            raise ValueError("History not found")

        # Decrypt existing data (if any) before updating
        history.decrypt_sensitive_data()

        history.flattenedResults = flattened_results
        history.updatedAt = datetime.now(UTC)
        # Use replace() to ensure encryption hook is triggered
        # Encryption happens automatically in @before_event hook
        await history.replace()
        logger.info(
            "Flattened results stored in history",
            extra={
                "history_id": str(history.id),
                "results_count": len(flattened_results),
            },
        )
        return history

    async def finalize_history(
        self,
        history_id: PydanticObjectId,
        *,
        total_sources: int,
        flattened_results: list[dict[str, Any]] | None = None,
    ) -> History:
        history = await History.get(history_id)
        if not history:
            raise ValueError("History not found")

        # Decrypt existing data before modifying
        history.decrypt_sensitive_data()

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

        # Recalculate counts from actual results to ensure accuracy
        # Try to decrypt if results appear to be encrypted
        if isinstance(history.results, str) and history._is_encrypted_string(
            history.results
        ):
            # Results are still encrypted - try to decrypt again
            try:
                history.decrypt_sensitive_data()
            except Exception as e:
                logger.warning(
                    f"Could not decrypt results for status calculation: {e}. "
                    "Using metadata counts instead."
                )

        if isinstance(history.results, list):
            successful_count = sum(1 for result in history.results if result.success)
            failed_count = sum(1 for result in history.results if not result.success)
            meta.successfulSources = successful_count
            meta.failedSources = failed_count
        else:
            # If results is encrypted or not a list, use existing metadata
            successful_count = meta.successfulSources
            failed_count = meta.failedSources

        # Determine status based on recalculated results
        # COMPLETED: all sources succeeded (no failures and at least one success)
        # PARTIAL: some sources failed but at least one succeeded
        # FAILED: all sources failed (no successes)
        # Always update status - never leave it as IN_PROGRESS after finalization
        if successful_count == 0 and failed_count > 0:
            history.status = "FAILED"
        elif failed_count > 0:
            history.status = "PARTIAL"
        elif successful_count > 0 and failed_count == 0:
            history.status = "COMPLETED"
        elif successful_count == 0 and failed_count == 0:
            # No results at all - mark as FAILED since nothing succeeded
            history.status = "FAILED"
        else:
            # Fallback: should not reach here, but ensure status is updated
            history.status = "COMPLETED" if failed_count == 0 else "PARTIAL"

        # Ensure status is never IN_PROGRESS after finalization
        if history.status == "IN_PROGRESS":
            logger.warning(
                f"History {history.id} status was still IN_PROGRESS after finalization. "
                f"Setting to COMPLETED based on counts: success={successful_count}, failed={failed_count}"
            )
            history.status = (
                "COMPLETED" if successful_count > 0 and failed_count == 0 else "PARTIAL"
            )

        # Store flattened results if provided
        if flattened_results is not None:
            history.flattenedResults = flattened_results

        history.updatedAt = datetime.now(UTC)
        # Use replace() to ensure encryption hook is triggered
        # Encryption happens automatically in @before_event hook
        await history.replace()
        logger.info(
            "History finalized",
            extra={
                "history_id": str(history.id),
                "status": history.status,
                "success_count": meta.successfulSources,
                "failed_count": meta.failedSources,
                "flattened_results_count": (
                    len(flattened_results) if flattened_results else 0
                ),
            },
        )
        return history

    async def get_history_by_id(self, history_id: PydanticObjectId) -> History | None:
        history = await History.get(history_id)
        if history:
            # Decrypt data after loading
            history.decrypt_sensitive_data()
        return history

    async def get_user_histories(
        self,
        user_id: PydanticObjectId,
        *,
        page: int = 1,
        size: int = 20,
        query_type: str | None = None,
    ) -> tuple[list[History], int]:
        skip = max(0, (page - 1) * size)
        cursor = History.find(History.userId == user_id)
        if query_type:
            cursor = cursor.find(History.queryType == query_type)
        cursor = cursor.sort("-createdAt")
        total = await cursor.count()
        items = await cursor.skip(skip).limit(size).to_list()

        # Decrypt all items after loading
        for item in items:
            item.decrypt_sensitive_data()

        return items, total

    async def get_histories_admin(
        self,
        *,
        user_id: PydanticObjectId | None = None,
        page: int = 1,
        size: int = 20,
        query_type: str | None = None,
    ) -> tuple[list[History], int]:
        """
        Get histories for admin. When user_id is provided, filter by user.
        Otherwise return all histories. Optionally filter by query_type.
        """
        skip = max(0, (page - 1) * size)
        if user_id is not None:
            cursor = History.find(History.userId == user_id)
        else:
            cursor = History.find()
        if query_type:
            cursor = cursor.find(History.queryType == query_type)
        cursor = cursor.sort("-createdAt")
        total = await cursor.count()
        items = await cursor.skip(skip).limit(size).to_list()

        for item in items:
            item.decrypt_sensitive_data()

        return items, total

    async def delete_all_user_history(
        self,
        user_id: PydanticObjectId,
    ) -> int:
        """
        Delete all history records for a specific user.

        Args:
            user_id: User ID whose history should be deleted

        Returns:
            Number of history records deleted
        """
        try:
            result = await History.find(History.userId == user_id).delete_many()
            deleted_count = result.deleted_count
            logger.info(
                "All user history deleted",
                extra={
                    "user_id": str(user_id),
                    "deleted_count": deleted_count,
                },
            )
            return deleted_count
        except Exception as e:
            logger.error(
                "Error deleting user history",
                extra={
                    "user_id": str(user_id),
                    "exception": type(e).__name__,
                },
            )
            raise
