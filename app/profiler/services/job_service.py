"""Job service - create jobs, resolve connectors, enqueue."""

from __future__ import annotations

import logging
from uuid import uuid4

from app.profiler.models.job import ProfilerJob
from app.profiler.models.target import ProfilerTarget
from app.profiler.services.redis_queue import ProfilerRedisQueue

logger = logging.getLogger(__name__)


class JobService:
    """Create and enqueue profiler jobs."""

    def __init__(self) -> None:
        self._queue = ProfilerRedisQueue()

    def _resolve_canonical_url(self, target: ProfilerTarget) -> str:
        """Resolve canonical URL from target (connector logic)."""
        from app.profiler.services.connectors import (
            BlogPublicConnector,
            FacebookPublicConnector,
            InstagramPublicConnector,
            LinkedInPublicConnector,
            RedditPublicConnector,
            XPublicConnector,
        )

        _CONNECTOR_MAP = {
            "x": XPublicConnector,
            "instagram": InstagramPublicConnector,
            "facebook": FacebookPublicConnector,
            "blog": BlogPublicConnector,
            "linkedin": LinkedInPublicConnector,
            "reddit": RedditPublicConnector,
        }
        connector_cls = _CONNECTOR_MAP.get(target.detected_source)
        if not connector_cls:
            return target.canonical_url
        connector = connector_cls()
        result = connector.resolve(target.input_value, target.target_type)
        return result.canonical_url

    async def enqueue_public_capture(
        self,
        case_id: str,
        target_id: str,
        org_id: str,
        created_by: str,
    ) -> ProfilerJob:
        """Create public_capture job and enqueue to Redis."""
        idempotency_key = f"capture:{case_id}:{target_id}:{uuid4().hex[:16]}"
        job = ProfilerJob(
            case_id=case_id,
            target_id=target_id,
            org_id=org_id,
            created_by=created_by,
            job_type="public_capture",
            status="queued",
            idempotency_key=idempotency_key,
            payload={"canonical_url": None},
        )
        target = await ProfilerTarget.get(target_id)
        if target:
            job.payload = {"canonical_url": target.canonical_url}
        await job.insert()
        await self._queue.enqueue(str(job.id))
        return job

    async def enqueue_inference(
        self,
        case_id: str,
        target_id: str,
        org_id: str,
        created_by: str,
        payload: dict,
    ) -> ProfilerJob:
        """Create inference job and enqueue to Redis."""
        idempotency_key = f"infer:{case_id}:{target_id}:{uuid4().hex[:16]}"
        job = ProfilerJob(
            case_id=case_id,
            target_id=target_id,
            org_id=org_id,
            created_by=created_by,
            job_type="inference",
            status="queued",
            idempotency_key=idempotency_key,
            payload=payload,
        )
        await job.insert()
        await self._queue.enqueue(str(job.id))
        return job
