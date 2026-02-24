"""
Admin Profiler Scrape Endpoints

Test-only endpoints to hit scrapers (Facebook, X, Instagram) directly without
authentication, authorization, or worker/Docker. For debugging and testing.

Endpoints:
- POST /admin/profiler/scrape - Scrape a profile URL via the specified connector
  - Optional upload=True: uploads scraped JSON to Azure Blob. Returns blob_path.
- POST /admin/profiler/normalize - Pull blob and run normalization synchronously
  (no Redis, no worker). Use after scrape+upload for fast testing.
- POST /admin/profiler/analyze - Run analyzers on normalized entities synchronously
  (no Redis, no worker). Use after normalize. Pass org_id, case_id, target_id from
  normalize response.

Warning: No auth. Use only in dev/test environments.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.profiler.models.job import ProfilerJob
from app.profiler.services.analyzer import run_all_analyzers
from app.profiler.services.connectors import (
    BlogPublicConnector,
    FacebookPublicConnector,
    InstagramPublicConnector,
    LinkedInPublicConnector,
    RedditPublicConnector,
    XPublicConnector,
)
from app.profiler.services.evidence_store import AzureBlobEvidenceStore
from app.profiler.services.inference_registry import get_inference_client
from app.profiler.services.normalizer_service import NormalizerService
from app.profiler.utils.hashing import sha256_bytes
from app.profiler.utils.url_detect import detect_source_by_hostname
from app.schemas.response import SuccessResponse

router = APIRouter()
logger = logging.getLogger(__name__)

ScraperType = Literal["x", "instagram", "facebook", "blog", "linkedin", "reddit"]

_CONNECTORS = {
    "x": XPublicConnector,
    "instagram": InstagramPublicConnector,
    "facebook": FacebookPublicConnector,
    "blog": BlogPublicConnector,
    "linkedin": LinkedInPublicConnector,
    "reddit": RedditPublicConnector,
}


class ProfilerScrapeRequest(BaseModel):
    """Request to scrape a profile via admin API."""

    type: ScraperType = Field(..., description="Scraper: x, instagram, or facebook")
    url: str = Field(
        ..., description="Full profile URL to scrape (e.g. https://x.com/username)"
    )
    upload: bool = Field(
        default=False,
        description="If True, upload scraped JSON to Azure Blob (same as collect API) for debugging upload issues.",
    )
    org_id: str | None = Field(
        default=None,
        description="Override org_id for blob path when upload=True (default: admin-debug-org)",
    )
    case_id: str | None = Field(
        default=None,
        description="Override case_id for blob path when upload=True (default: admin-debug-case)",
    )
    target_id: str | None = Field(
        default=None,
        description="Override target_id for blob path when upload=True (default: admin-debug-target)",
    )
    job_id: str | None = Field(
        default=None,
        description="Override job_id for blob path when upload=True (default: admin-debug-job)",
    )


def _scraper_result_to_dict(result: Any) -> dict[str, Any]:
    """Convert ScraperResult dataclass to JSON-serializable dict."""
    return {
        "status": result.status,
        "extracted": result.extracted,
        "reason": result.reason,
    }


@router.post("/scrape", response_model=SuccessResponse[dict[str, Any]])
async def admin_profiler_scrape(request: ProfilerScrapeRequest):
    """
    Scrape a profile URL directly using the specified connector.
    No auth, no worker, no DB. Returns raw scraper result for testing.

    Set upload=True to also upload the scraped JSON to Azure Blob (same logic as
    profiler/cases/.../targets/.../collect) for debugging upload issues.
    """
    connector_cls = _CONNECTORS.get(request.type)
    if not connector_cls:
        raise HTTPException(
            status_code=400,
            detail="Invalid type. Must be one of: x, instagram, facebook, blog, linkedin, reddit",
        )

    connector = connector_cls()
    result = await connector.fetch_and_parse(request.url)

    # Log result for visibility in console
    logger.info(
        "Admin profiler scrape completed",
        extra={
            "type": request.type,
            "url": request.url[:80],
            "status": result.status,
            "reason": result.reason,
        },
    )
    print(
        f"[admin/profiler/scrape] type={request.type} url={request.url} -> status={result.status}"
    )  # noqa: T201

    data: dict[str, Any] = {
        "type": request.type,
        "url": request.url,
        "result": _scraper_result_to_dict(result),
    }

    # Optional: upload to Azure Blob (same code path as collect API worker) for debugging
    if request.upload and result.status == "collected" and result.extracted:
        org_id = request.org_id or "admin-debug-org"
        case_id = request.case_id or "admin-debug-case"
        target_id = request.target_id or "admin-debug-target"
        job_id = request.job_id or "admin-debug-job"

        try:
            extracted = result.extracted
            json_bytes = json.dumps(
                extracted, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            sha256 = sha256_bytes(json_bytes)

            evidence_store = AzureBlobEvidenceStore()
            blob_path = await evidence_store.put_json_evidence(
                org_id=org_id,
                case_id=case_id,
                target_id=target_id,
                job_id=job_id,
                sha256=sha256,
                data=extracted,
            )

            data["upload"] = {"success": True, "blob_path": blob_path}
            print(
                f"[admin/profiler/scrape] Azure upload OK -> {blob_path}"
            )  # noqa: T201
        except Exception as e:
            logger.exception("Admin profiler scrape: Azure blob upload failed")
            data["upload"] = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            print(f"[admin/profiler/scrape] Azure upload FAILED: {e}")  # noqa: T201

    return SuccessResponse(
        message="Profiler scrape completed",
        data=data,
    )


def _parse_object_id(val: str | None) -> ObjectId | None:
    """Return ObjectId from 24-char hex string, or None if invalid."""
    if not val or len(val) != 24:
        return None
    try:
        return ObjectId(val)
    except Exception:
        return None


class ProfilerNormalizeRequest(BaseModel):
    """Request to run normalization from a blob path."""

    blob_path: str = Field(
        ...,
        description="Blob path from scrape+upload (e.g. profiler/admin-debug-org/.../xxx.json)",
    )
    url: str = Field(
        ...,
        description="Profile URL (for source detection and entity context)",
    )
    org_id: str | None = Field(
        default=None,
        description="24-char hex ObjectId. If omitted, generated for test entities.",
    )
    case_id: str | None = Field(
        default=None,
        description="24-char hex ObjectId. If omitted, generated for test entities.",
    )
    target_id: str | None = Field(
        default=None,
        description="24-char hex ObjectId. If omitted, generated for test entities.",
    )
    source: str | None = Field(
        default=None,
        description="Platform override: x, instagram, facebook. Inferred from url if omitted.",
    )


@router.post("/normalize", response_model=SuccessResponse[dict[str, Any]])
async def admin_profiler_normalize(request: ProfilerNormalizeRequest):
    """
    Pull JSON from Azure Blob and run normalization synchronously.
    No Redis, no worker. Use after POST /admin/profiler/scrape with upload=True.

    Returns entities_created count. Requires MongoDB (entities are stored).
    """
    org_oid = _parse_object_id(request.org_id) or ObjectId()
    case_oid = _parse_object_id(request.case_id) or ObjectId()
    target_oid = _parse_object_id(request.target_id) or ObjectId()

    try:
        normalizer = NormalizerService()
        count = await normalizer.normalize_from_blob(
            blob_path=request.blob_path,
            url=request.url,
            org_id=org_oid,
            case_id=case_oid,
            target_id=target_oid,
            source=request.source,
        )
        source_detected = request.source or detect_source_by_hostname(request.url)
        return SuccessResponse(
            message="Normalization completed",
            data={
                "entities_created": count,
                "blob_path": request.blob_path,
                "url": request.url,
                "source": source_detected,
                "org_id": str(org_oid),
                "case_id": str(case_oid),
                "target_id": str(target_oid),
            },
        )
    except Exception as e:
        logger.exception("Admin profiler normalize failed")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
            },
        ) from e


class ProfilerAnalyzeRequest(BaseModel):
    """Request to run analyzers on normalized entities."""

    target_id: str = Field(
        ...,
        description="24-char hex ObjectId. Must match target_id from normalize response.",
    )
    org_id: str | None = Field(
        default=None,
        description="24-char hex ObjectId. Use same as normalize response.",
    )
    case_id: str | None = Field(
        default=None,
        description="24-char hex ObjectId. Use same as normalize response.",
    )


@router.post("/analyze", response_model=SuccessResponse[dict[str, Any]])
async def admin_profiler_analyze(request: ProfilerAnalyzeRequest):
    """
    Run all analyzers on normalized entities synchronously.
    No Redis, no worker. Use after POST /admin/profiler/normalize.

    Pass org_id, case_id, target_id from the normalize response so artifacts
    are linked correctly. Entities must exist in MongoDB (run normalize first).

    Returns artifacts_created count and artifact types.
    """
    target_oid = _parse_object_id(request.target_id)
    if not target_oid:
        raise HTTPException(
            status_code=400,
            detail="target_id must be a valid 24-char hex ObjectId",
        )
    org_oid = _parse_object_id(request.org_id) or ObjectId()
    case_oid = _parse_object_id(request.case_id) or ObjectId()

    try:
        job = ProfilerJob.model_construct(
            id=ObjectId(),
            org_id=org_oid,
            case_id=case_oid,
            target_id=target_oid,
            created_by=org_oid,
            job_type="analyze",
            status="queued",
        )
        inference_client = get_inference_client()
        artifacts = await run_all_analyzers(job, inference_client)
        artifact_types = [a.artifact_type for a in artifacts]
        return SuccessResponse(
            message="Analysis completed",
            data={
                "artifacts_created": len(artifacts),
                "artifact_types": artifact_types,
                "org_id": str(org_oid),
                "case_id": str(case_oid),
                "target_id": str(target_oid),
            },
        )
    except Exception as e:
        logger.exception("Admin profiler analyze failed")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
            },
        ) from e
