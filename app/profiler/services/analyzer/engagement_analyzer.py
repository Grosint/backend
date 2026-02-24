"""Engagement analyzer - top interactors weighted by type and recency."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.entities.interaction_entity import InteractionEntity

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

TYPE_WEIGHTS: dict[str, int] = {"reply": 3, "comment": 2, "mention": 1, "tag": 1}
RECENCY_DAYS = 30
RECENCY_BOOST = 1.5
TOP_N = 10


class EngagementAnalyzer:
    async def analyze(
        self,
        job: ProfilerJob,
        inference_client: InferenceClient,
    ) -> ProfilerArtifact | None:
        interactions = await InteractionEntity.find(
            InteractionEntity.target_id == job.target_id,
        ).to_list()

        if not interactions:
            return None

        now = datetime.now(UTC)
        cutoff = now - timedelta(days=RECENCY_DAYS)
        scores: dict[str, float] = defaultdict(float)

        for ix in interactions:
            created = ix.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            base = TYPE_WEIGHTS.get(ix.interaction_type, 1)
            multiplier = RECENCY_BOOST if created >= cutoff else 1.0
            scores[ix.counterparty_profile_id] += base * multiplier

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]

        return ProfilerArtifact(
            org_id=job.org_id,
            case_id=job.case_id,
            target_id=job.target_id,
            job_id=job.id,
            artifact_type="engagement",
            version="v1",
            payload={
                "top_interactors": [
                    {"profile_id": pid, "score": round(score, 2)}
                    for pid, score in ranked
                ],
                "total_interactions": len(interactions),
            },
        )
