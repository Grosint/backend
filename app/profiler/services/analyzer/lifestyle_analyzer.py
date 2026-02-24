"""Lifestyle analyzer - review categories and price distributions."""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.entities.review_entity import ReviewEntity

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)


class LifestyleAnalyzer:
    async def analyze(
        self,
        job: ProfilerJob,
        inference_client: InferenceClient,
    ) -> ProfilerArtifact | None:
        reviews = await ReviewEntity.find(
            ReviewEntity.target_id == job.target_id,
        ).to_list()

        if not reviews:
            return None

        category_counts: Counter[str] = Counter()
        price_counts: Counter[str] = Counter()
        ratings: list[float] = []

        for r in reviews:
            if r.category:
                category_counts[r.category] += 1
            if r.price_range:
                price_counts[r.price_range] += 1
            if r.rating is not None:
                ratings.append(r.rating)

        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        return ProfilerArtifact(
            org_id=job.org_id,
            case_id=job.case_id,
            target_id=job.target_id,
            job_id=job.id,
            artifact_type="lifestyle",
            version="v1",
            payload={
                "category_distribution": dict(category_counts.most_common(20)),
                "price_distribution": dict(price_counts.most_common(10)),
                "average_rating": avg_rating,
                "total_reviews": len(reviews),
            },
        )
