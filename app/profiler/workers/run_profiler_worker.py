#!/usr/bin/env python3
"""
Profiler worker - consumes Redis stream, runs the full pipeline:
  public_capture → normalize → analyze → (inference)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure project root (backend/) is on path
_env_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_env_dir))

# Load .env before any app imports
from dotenv import load_dotenv  # noqa: E402

load_dotenv(_env_dir / ".env")

from app.core.config import settings  # noqa: E402
from app.core.database import connect_to_mongo  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.profiler.models.artifact import ProfilerArtifact  # noqa: E402
from app.profiler.models.job import ProfilerJob  # noqa: E402
from app.profiler.models.target import ProfilerTarget  # noqa: E402
from app.profiler.schemas.inference import InferenceRequest  # noqa: E402
from app.profiler.services.collector_service import CollectorService  # noqa: E402
from app.profiler.services.inference_registry import get_inference_client  # noqa: E402
from app.profiler.services.normalizer_service import NormalizerService  # noqa: E402
from app.profiler.services.profiler_service import ProfilerService  # noqa: E402
from app.profiler.services.redis_queue import ProfilerRedisQueue  # noqa: E402

setup_logging()

_PROFILER_PREFIX = "[ProfilerWorker] "


class ProfilerLogPrefixFilter(logging.Filter):
    """Prepends [ProfilerWorker] to logs from profiler modules."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name.startswith("app.profiler") or record.name == "__main__":
            record.msg = _PROFILER_PREFIX + str(record.msg)
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(ProfilerLogPrefixFilter())

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


async def _enqueue_next(
    parent: ProfilerJob,
    job_type: str,
    payload: dict,
    queue: ProfilerRedisQueue,
) -> None:
    """Create and enqueue the next job in the pipeline."""
    next_job = ProfilerJob(
        case_id=parent.case_id,
        target_id=parent.target_id,
        org_id=parent.org_id,
        created_by=parent.created_by,
        job_type=job_type,
        status="queued",
        payload=payload,
    )
    await next_job.insert()
    await queue.enqueue(str(next_job.id))
    logger.info(
        "Next pipeline job enqueued",
        extra={
            "parent_job_id": str(parent.id),
            "next_type": job_type,
            "next_id": str(next_job.id),
        },
    )


# ---------------------------------------------------------------------------
# Job handlers
# ---------------------------------------------------------------------------


async def run_public_capture(job: ProfilerJob) -> None:
    """Execute public_capture job: fetch, store evidence, create artifacts."""
    collector = CollectorService()
    profiler_svc = ProfilerService()

    canonical_url = (job.payload or {}).get("canonical_url")
    target = await ProfilerTarget.get(job.target_id)
    if not canonical_url:
        if not target:
            job.status = "failed"
            job.error = {"code": "TARGET_NOT_FOUND", "message": "Target not found"}
            job.finished_at = datetime.now(UTC)
            await job.save()
            return
        canonical_url = target.canonical_url

    detected_source = (target.detected_source if target else "unknown") or "unknown"

    if detected_source in ("facebook", "instagram", "x"):
        result_doc = await _run_scraper_capture(
            job, canonical_url, detected_source, profiler_svc
        )
    else:
        result_doc = await _run_http_capture(
            job, canonical_url, collector, profiler_svc
        )

    if result_doc is None:
        return

    await result_doc.insert()
    await profiler_svc.write_artifacts(result_doc)

    job.status = "succeeded"
    job.finished_at = datetime.now(UTC)
    job.metrics = job.metrics or {}
    job.metrics["source_documents"] = 1
    await job.save()


async def _run_scraper_capture(
    job: ProfilerJob,
    canonical_url: str,
    detected_source: str,
    profiler_svc: ProfilerService,
):
    """Run platform-specific scraper connector. Returns ProfilerSourceDocument or None."""
    import json

    from app.profiler.models.source_document import ProfilerSourceDocument
    from app.profiler.services.connectors import (
        BlogPublicConnector,
        FacebookPublicConnector,
        InstagramPublicConnector,
        LinkedInPublicConnector,
        RedditPublicConnector,
        XPublicConnector,
    )
    from app.profiler.services.evidence_store import AzureBlobEvidenceStore
    from app.profiler.utils.hashing import sha256_bytes
    from app.profiler.utils.now import utc_now

    connector_map = {
        "facebook": FacebookPublicConnector,
        "instagram": InstagramPublicConnector,
        "x": XPublicConnector,
        "blog": BlogPublicConnector,
        "linkedin": LinkedInPublicConnector,
        "reddit": RedditPublicConnector,
    }
    connector_cls = connector_map.get(detected_source)
    if not connector_cls:
        return None

    connector = connector_cls()
    result = await connector.fetch_and_parse(canonical_url)

    if result.status == "not_collectible":
        job.status = "not_collectible"
        job.error = {"code": "NOT_COLLECTIBLE", "reason": result.reason}
        job.finished_at = datetime.now(UTC)
        await job.save()
        return None

    if not result.extracted:
        job.status = "failed"
        job.error = {"code": "NO_EXTRACTED_DATA", "message": "Scraper returned no data"}
        job.finished_at = datetime.now(UTC)
        await job.save()
        return None

    extracted = result.extracted
    provenance = extracted.get("provenance", {})
    url = provenance.get("raw_url", canonical_url)
    http_status = provenance.get("http_status", 200)
    headers = provenance.get("headers", {})

    json_bytes = json.dumps(
        extracted, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    sha256 = sha256_bytes(json_bytes)
    captured_at = utc_now()

    evidence_store = AzureBlobEvidenceStore()
    blob_path = await evidence_store.put_json_evidence(
        org_id=str(job.org_id),
        case_id=str(job.case_id),
        target_id=str(job.target_id),
        job_id=str(job.id),
        sha256=sha256,
        data=extracted,
    )

    doc = ProfilerSourceDocument(
        org_id=job.org_id,
        case_id=job.case_id,
        target_id=job.target_id,
        job_id=job.id,
        url=url,
        captured_at=captured_at,
        http_status=http_status,
        headers=headers,
        content_type="application/json",
        fetch_method="scrape",
        sha256=sha256,
        blob_path=blob_path,
        parser_version=provenance.get("parser_version", "v1"),
    )
    return doc


async def _run_http_capture(
    job: ProfilerJob,
    canonical_url: str,
    collector: CollectorService,
    profiler_svc: ProfilerService,
):
    """Run generic HTTP collector. Returns ProfilerSourceDocument or None."""
    result = await collector.collect(
        url=canonical_url,
        org_id=str(job.org_id),
        case_id=str(job.case_id),
        target_id=str(job.target_id),
        job_id=str(job.id),
    )

    if result.status == "not_collectible":
        job.status = "not_collectible"
        job.error = {"code": "NOT_COLLECTIBLE", "reason": result.reason}
        job.finished_at = datetime.now(UTC)
        await job.save()
        return None

    return result.source_document


async def run_normalize(job: ProfilerJob) -> None:
    """Execute normalize job: parse HTML → canonical entities."""
    normalizer = NormalizerService()
    total = await normalizer.normalize_job(job)

    job.status = "succeeded"
    job.finished_at = datetime.now(UTC)
    job.metrics = job.metrics or {}
    job.metrics["entities_created"] = total
    await job.save()
    logger.info(
        "Normalize job complete",
        extra={"job_id": str(job.id), "entities_created": total},
    )


async def run_analyze(job: ProfilerJob) -> None:
    """Execute analyze job: run all analyzers → ProfilerArtifacts."""
    from app.profiler.services.analyzer import run_all_analyzers

    client = get_inference_client()
    artifacts = await run_all_analyzers(job, client)

    job.status = "succeeded"
    job.finished_at = datetime.now(UTC)
    job.metrics = job.metrics or {}
    job.metrics["artifacts_created"] = len(artifacts)
    await job.save()
    logger.info(
        "Analyze job complete",
        extra={"job_id": str(job.id), "artifacts_created": len(artifacts)},
    )


async def run_inference(job: ProfilerJob) -> None:
    """Execute inference job: policy gate, call client, store artifact."""
    payload = job.payload or {}
    if "context" not in payload:
        payload["context"] = {}
    payload["context"]["job_id"] = str(job.id)
    try:
        req = InferenceRequest(**payload)
    except Exception as e:
        job.status = "failed"
        job.error = {"code": "INVALID_PAYLOAD", "message": str(e)}
        job.finished_at = datetime.now(UTC)
        await job.save()
        return

    # Policy gate: face_cluster requires high policy tier
    policy_tier = (req.context.policy_tier or "default").lower()
    if req.task_type == "face_cluster" and policy_tier not in ("high", "admin"):
        client = get_inference_client()
        resp = await client.run(req)
        resp.policy_flags = resp.policy_flags + ["SENSITIVE_TASK_BLOCKED"]
    else:
        client = get_inference_client()
        resp = await client.run(req)

    evidence_ids = []
    for inp in req.inputs:
        if inp.ref_type == "source_document_id":
            evidence_ids.append(inp.ref)

    artifact = ProfilerArtifact(
        org_id=job.org_id,
        case_id=job.case_id,
        target_id=job.target_id,
        job_id=job.id,
        artifact_type="inference_result",
        payload={
            "task_type": req.task_type,
            "inputs": [i.model_dump() for i in req.inputs],
            "enabled": resp.enabled,
            "output": resp.output,
            "confidence": resp.confidence,
            "explanations": resp.explanations,
            "model_version": resp.model_version,
            "policy_flags": resp.policy_flags,
        },
        evidence_ids=evidence_ids,
    )
    await artifact.insert()

    job.status = "succeeded"
    job.finished_at = datetime.now(UTC)
    job.metrics = job.metrics or {}
    job.metrics["inference_enabled"] = resp.enabled
    await job.save()


# ---------------------------------------------------------------------------
# Message processing (pipeline orchestration)
# ---------------------------------------------------------------------------


async def process_message(msg_id: str, job_id: str, queue: ProfilerRedisQueue) -> bool:
    """
    Process single job. Returns True if message was handled (ack or re-queue).
    Chains pipeline: capture → normalize → analyze.
    """
    job = await ProfilerJob.get(job_id)
    if not job:
        logger.warning("Job not found", extra={"job_id": job_id})
        await queue.ack(msg_id)
        return True

    job.status = "running"
    job.started_at = datetime.now(UTC)
    await job.save()

    try:
        if job.job_type == "public_capture":
            await run_public_capture(job)
            if job.status == "succeeded":
                await _enqueue_next(
                    job, "normalize", {"capture_job_id": str(job.id)}, queue
                )

        elif job.job_type == "normalize":
            await run_normalize(job)
            if job.status == "succeeded":
                await _enqueue_next(
                    job, "analyze", {"normalize_job_id": str(job.id)}, queue
                )

        elif job.job_type == "analyze":
            await run_analyze(job)

        elif job.job_type == "inference":
            await run_inference(job)

        else:
            job.status = "failed"
            job.error = {"code": "UNKNOWN_JOB_TYPE", "message": str(job.job_type)}
            job.finished_at = datetime.now(UTC)
            await job.save()

    except Exception as e:
        logger.error(
            "Job execution failed",
            extra={"job_id": job_id, "error": str(e)},
            exc_info=True,
        )
        job.attempts = (job.attempts or 0) + 1
        job.status = "failed" if job.attempts >= job.max_attempts else "queued"
        job.error = {"code": "EXCEPTION", "message": str(e)}
        if job.attempts >= job.max_attempts:
            job.finished_at = datetime.now(UTC)
        await job.save()
        if job.attempts < job.max_attempts:
            await queue.enqueue(job_id)
    finally:
        await queue.ack(msg_id)

    return True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def run_worker() -> None:
    """Main worker loop."""
    await connect_to_mongo(process="Worker Process")
    queue = ProfilerRedisQueue()
    consumer = settings.PROFILER_REDIS_CONSUMER_NAME
    await queue.ensure_group()

    logger.info("Profiler worker started", extra={"consumer": consumer})

    while True:
        try:
            result = await queue.claim_next(consumer, block_ms=5000)
            if result:
                msg_id, job_id = result
                await process_message(msg_id, job_id, queue)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Worker loop error", extra={"error": str(e)}, exc_info=True)
            await asyncio.sleep(5)

    await queue.close()
    logger.info("Profiler worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
