"""Redis Streams queue for profiler jobs."""

from __future__ import annotations

import logging

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Keys for message payload
JOB_ID_KEY = "job_id"


class ProfilerRedisQueue:
    """Redis Streams-based job queue for profiler workers."""

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        stream: str | None = None,
        consumer_group: str | None = None,
    ) -> None:
        self._redis_url = redis_url or settings.PROFILER_REDIS_URL
        self._stream = stream or settings.PROFILER_REDIS_STREAM
        self._consumer_group = consumer_group or settings.PROFILER_REDIS_CONSUMER_GROUP
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                self._redis_url,
                decode_responses=True,
            )
        return self._client

    async def ensure_group(
        self, stream: str | None = None, group: str | None = None
    ) -> None:
        """Ensure consumer group exists; create if not."""
        s = stream or self._stream
        g = group or self._consumer_group
        try:
            client = await self._get_client()
            await client.xgroup_create(s, g, id="0", mkstream=True)
            logger.info("Redis consumer group created", extra={"stream": s, "group": g})
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(
                    "Consumer group already exists", extra={"stream": s, "group": g}
                )
            else:
                logger.warning("Redis xgroup_create", extra={"error": str(e)})
                raise
        except Exception as e:
            logger.error(
                "Redis ensure_group failed", extra={"error": str(e)}, exc_info=True
            )
            raise

    async def enqueue(self, job_id: str, stream: str | None = None) -> str | None:
        """Add job to stream. Returns message ID or None on failure."""
        s = stream or self._stream
        try:
            client = await self._get_client()
            msg_id = await client.xadd(s, {JOB_ID_KEY: job_id})
            logger.info("Job enqueued", extra={"job_id": job_id, "msg_id": msg_id})
            return msg_id
        except Exception as e:
            logger.error(
                "Redis enqueue failed", extra={"job_id": job_id, "error": str(e)}
            )
            return None

    async def claim_next(
        self,
        consumer_name: str,
        stream: str | None = None,
        group: str | None = None,
        block_ms: int = 5000,
    ) -> tuple[str, str] | None:
        """
        Claim next message from stream for this consumer.
        Returns (msg_id, job_id) or None if no message.
        """
        s = stream or self._stream
        g = group or self._consumer_group
        try:
            client = await self._get_client()
            results = await client.xreadgroup(
                groupname=g,
                consumername=consumer_name,
                streams={s: ">"},
                count=1,
                block=block_ms,
            )
            if not results:
                return None
            for _stream_name, messages in results:
                for msg_id, data in messages:
                    job_id = data.get(JOB_ID_KEY)
                    if job_id:
                        return (msg_id, job_id)
            return None
        except Exception as e:
            logger.error(
                "Redis claim_next failed",
                extra={"consumer": consumer_name, "error": str(e)},
                exc_info=True,
            )
            raise

    async def ack(
        self,
        msg_id: str,
        stream: str | None = None,
        group: str | None = None,
    ) -> bool:
        """Acknowledge message processing."""
        s = stream or self._stream
        g = group or self._consumer_group
        try:
            client = await self._get_client()
            await client.xack(s, g, msg_id)
            return True
        except Exception as e:
            logger.error("Redis ack failed", extra={"msg_id": msg_id, "error": str(e)})
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
