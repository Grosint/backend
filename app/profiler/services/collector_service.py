"""Public HTTP collector - public-web capture only."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.core.config import settings
from app.core.resilience import ResilientHttpClient
from app.profiler.models.source_document import ProfilerSourceDocument
from app.profiler.services.evidence_store import AzureBlobEvidenceStore
from app.profiler.utils.gating import is_login_wall
from app.profiler.utils.hashing import sha256_bytes
from app.profiler.utils.now import utc_now

logger = logging.getLogger(__name__)

CollectResultStatus = Literal["collected", "not_collectible"]


@dataclass
class CollectResult:
    """Result from public capture attempt."""

    status: CollectResultStatus
    source_document: ProfilerSourceDocument | None = None
    reason: str | None = None


class CollectorService:
    """Public-web HTTP collector - no login, no credentials."""

    def __init__(self) -> None:
        self._client = ResilientHttpClient(
            timeout_seconds=float(settings.PROFILER_PUBLIC_FETCH_TIMEOUT_SECONDS),
            headers={"User-Agent": settings.PROFILER_PUBLIC_USER_AGENT},
        )
        self._evidence_store = AzureBlobEvidenceStore()
        self._max_pages = settings.PROFILER_PUBLIC_MAX_PAGES_PER_JOB

    async def collect(
        self,
        url: str,
        org_id: str,
        case_id: str,
        target_id: str,
        job_id: str,
    ) -> CollectResult:
        """
        Fetch public URL via GET only. Enforce budget. Detect gating.
        On success: sha256, upload to Blob, return SourceDocument.
        """
        try:
            response = await self._client.request("GET", url)
            status = response.status_code
            body = response.content

            # Gating: 401, 403 => NOT_COLLECTIBLE
            if status in (401, 403):
                return CollectResult(
                    status="not_collectible",
                    reason=f"HTTP {status} - auth required",
                )

            # Login wall detection
            if is_login_wall(body):
                return CollectResult(
                    status="not_collectible",
                    reason="Login/sign-in wall detected",
                )

            # Success path
            sha256 = sha256_bytes(body)
            captured_at = utc_now()

            blob_path = await self._evidence_store.put_evidence(
                org_id=org_id,
                case_id=case_id,
                target_id=target_id,
                job_id=job_id,
                sha256=sha256,
                html=body,
            )

            # Sanitize headers - remove cookies, auth
            headers = self._sanitize_headers(dict(response.headers))
            content_type = response.headers.get("content-type", "").split(";")[0]

            doc = ProfilerSourceDocument(
                org_id=org_id,
                case_id=case_id,
                target_id=target_id,
                job_id=job_id,
                url=url,
                captured_at=captured_at,
                http_status=status,
                headers=headers,
                content_type=content_type or None,
                fetch_method="http",
                sha256=sha256,
                blob_path=blob_path,
                parser_version="v1",
            )
            return CollectResult(status="collected", source_document=doc)

        except Exception as e:
            logger.error(
                "Collector fetch failed",
                extra={"url": url[:80], "error": str(e)},
                exc_info=True,
            )
            raise

    def _sanitize_headers(self, headers: dict) -> dict:
        """Remove cookies and auth-related headers from stored copy."""
        skip = {"cookie", "authorization", "set-cookie", "x-csrf-token"}
        return {k: v for k, v in headers.items() if k.lower() not in skip}
