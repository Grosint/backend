"""Activity analyzer - temporal patterns across posts and comments."""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.entities.comment_entity import CommentEntity
from app.profiler.models.entities.post_entity import PostEntity

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


class ActivityAnalyzer:
    async def analyze(
        self,
        job: ProfilerJob,
        inference_client: InferenceClient,
    ) -> ProfilerArtifact | None:
        posts = await PostEntity.find(PostEntity.target_id == job.target_id).to_list()
        comments = await CommentEntity.find(
            CommentEntity.target_id == job.target_id
        ).to_list()

        if not posts and not comments:
            return None

        day_of_week: Counter[int] = Counter()
        hour_of_day: Counter[int] = Counter()
        by_source: Counter[str] = Counter()

        for p in posts:
            day_of_week[p.created_at.weekday()] += 1
            hour_of_day[p.created_at.hour] += 1
            by_source[p.source] += 1

        for c in comments:
            day_of_week[c.created_at.weekday()] += 1
            hour_of_day[c.created_at.hour] += 1
            by_source[c.source] += 1

        return ProfilerArtifact(
            org_id=job.org_id,
            case_id=job.case_id,
            target_id=job.target_id,
            job_id=job.id,
            artifact_type="activity",
            version="v1",
            payload={
                "posts_by_day_of_week": {
                    DAY_NAMES[d]: count for d, count in sorted(day_of_week.items())
                },
                "posts_by_hour": {
                    str(h): count for h, count in sorted(hour_of_day.items())
                },
                "counts_by_source": dict(by_source),
                "total_posts": len(posts),
                "total_comments": len(comments),
            },
        )
