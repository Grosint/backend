from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from beanie import PydanticObjectId

from app.core.resilience import ConcurrencyLimiter
from app.models.history import HistorySourceResult
from app.services.history_service import HistoryService

logger = logging.getLogger(__name__)


class GenericOrchestrator:
    """
    Runs multiple async callables (typically adapter calls) in parallel with a concurrency limit,
    collects per-source results, and persists a history document.
    Each callable should return a normalized dict: {success, data?, error_code?, message?}
    """

    def __init__(self, *, limiter: ConcurrencyLimiter | None = None):
        self._limiter = limiter or ConcurrencyLimiter()
        self._history_service = HistoryService()

    async def execute(
        self,
        *,
        user_id: PydanticObjectId | None,
        query_type: str,
        query_input: dict[str, Any] | str,
        tasks: Sequence[tuple[str, Callable[[], Awaitable[dict[str, Any]]]]],
    ) -> dict[str, Any]:
        history = await self._history_service.create_history(
            user_id=user_id, query_type=query_type, query_input=query_input
        )

        async def run_single(name: str, fn: Callable[[], Awaitable[dict[str, Any]]]):
            start = time.perf_counter()
            try:
                async with self._limiter.slot():
                    result = await fn()
                latency_ms = int((time.perf_counter() - start) * 1000)
                await self._history_service.add_result(
                    history.id,  # type: ignore[arg-type]
                    result=HistorySourceResult(
                        source=name,
                        success=bool(result.get("success", False)),
                        latencyMs=latency_ms,
                        data=result.get("data"),
                        errorCode=result.get("error_code"),
                        message=result.get("message"),
                    ),
                )
                logger.info(
                    "Orchestrator task completed",
                    extra={
                        "history_id": str(history.id),
                        "source": name,
                        "success": result.get("success", False),
                        "latency_ms": latency_ms,
                    },
                )
            except Exception as e:
                latency_ms = int((time.perf_counter() - start) * 1000)
                await self._history_service.add_result(
                    history.id,  # type: ignore[arg-type]
                    result=HistorySourceResult(
                        source=name,
                        success=False,
                        latencyMs=latency_ms,
                        data=None,
                        errorCode=type(e).__name__,
                        message=str(e),
                    ),
                )
                logger.error(
                    "Orchestrator task failed",
                    extra={
                        "history_id": str(history.id),
                        "source": name,
                        "exception": type(e).__name__,
                    },
                )

        await asyncio.gather(*(run_single(name, fn) for name, fn in tasks))

        await self._history_service.finalize_history(
            history.id, total_sources=len(tasks)
        )

        # Return a concise payload for immediate response; client can fetch full history by ID
        return {
            "history_id": str(history.id),
            "status": (await self._history_service.get_history_by_id(history.id)).status,  # type: ignore[attr-defined]
        }
