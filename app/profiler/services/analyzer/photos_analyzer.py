"""Photos analyzer - media timeline with optional inference hook."""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.entities.media_entity import MediaEntity
from app.profiler.schemas.inference import (
    InferenceContext,
    InferenceInputRef,
    InferenceRequest,
)

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)


class PhotosAnalyzer:
    async def analyze(
        self,
        job: ProfilerJob,
        inference_client: InferenceClient,
    ) -> ProfilerArtifact | None:
        media = await MediaEntity.find(
            MediaEntity.target_id == job.target_id,
            MediaEntity.media_type == "image",
        ).to_list()

        if not media:
            return None

        monthly: Counter[str] = Counter()
        for m in media:
            monthly[m.created_at.strftime("%Y-%m")] += 1

        timeline = [{"month": k, "count": v} for k, v in sorted(monthly.items())]

        inference_result: dict | None = None
        if media:
            try:
                refs = [
                    InferenceInputRef(ref_type="blob_path", ref=m.blob_path)
                    for m in media[:10]
                ]
                req = InferenceRequest(
                    task_type="image_summary",
                    inputs=refs,
                    context=InferenceContext(
                        org_id=str(job.org_id),
                        case_id=str(job.case_id),
                        target_id=str(job.target_id),
                        job_id=str(job.id),
                    ),
                )
                resp = await inference_client.run(req)
                if resp.enabled:
                    inference_result = resp.output
            except Exception:
                logger.debug("Inference hook skipped for photos", exc_info=True)

        return ProfilerArtifact(
            org_id=job.org_id,
            case_id=job.case_id,
            target_id=job.target_id,
            job_id=job.id,
            artifact_type="photos_summary",
            version="v1",
            payload={
                "total_images": len(media),
                "upload_timeline": timeline,
                "inference_result": inference_result,
            },
        )
