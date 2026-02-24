"""Hashtags analyzer - frequency counts and burst detection."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.entities.tag_entity import TagEntity

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)


class HashtagsAnalyzer:
    async def analyze(
        self,
        job: ProfilerJob,
        inference_client: InferenceClient,
    ) -> ProfilerArtifact | None:
        tags = await TagEntity.find(TagEntity.target_id == job.target_id).to_list()

        if not tags:
            return None

        freq: Counter[str] = Counter()
        monthly: dict[str, Counter[str]] = defaultdict(Counter)

        for t in tags:
            freq[t.tag] += 1
            month_key = t.created_at.strftime("%Y-%m")
            monthly[month_key][t.tag] += 1

        top_tags = freq.most_common(50)

        # Burst detection: months where a tag appeared at >= 2x its average frequency
        bursts: list[dict] = []
        for tag, total in top_tags[:20]:
            months_with = {m: monthly[m][tag] for m in monthly if monthly[m][tag] > 0}
            if not months_with:
                continue
            avg = total / max(len(months_with), 1)
            for month, count in months_with.items():
                if count >= avg * 2 and count >= 3:
                    bursts.append({"tag": tag, "month": month, "count": count})

        return ProfilerArtifact(
            org_id=job.org_id,
            case_id=job.case_id,
            target_id=job.target_id,
            job_id=job.id,
            artifact_type="hashtags",
            version="v1",
            payload={
                "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
                "bursts": sorted(bursts, key=lambda b: b["count"], reverse=True),
                "total_tags": sum(freq.values()),
            },
        )
