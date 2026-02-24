"""Comments analyzer - n-gram analysis with optional inference hook."""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.entities.comment_entity import CommentEntity
from app.profiler.schemas.inference import (
    InferenceContext,
    InferenceInputRef,
    InferenceRequest,
)

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)


class CommentsAnalyzer:
    async def analyze(
        self,
        job: ProfilerJob,
        inference_client: InferenceClient,
    ) -> ProfilerArtifact | None:
        comments = await CommentEntity.find(
            CommentEntity.target_id == job.target_id,
        ).to_list()

        if not comments:
            return None

        all_text = " ".join(c.text for c in comments if c.text)
        bigrams = self._top_ngrams(all_text, n=2, top_k=20)
        trigrams = self._top_ngrams(all_text, n=3, top_k=10)

        inference_summary: dict | None = None
        if all_text:
            try:
                req = InferenceRequest(
                    task_type="text_summary",
                    inputs=[
                        InferenceInputRef(
                            ref_type="entity_id", ref="comments_aggregate"
                        )
                    ],
                    context=InferenceContext(
                        org_id=str(job.org_id),
                        case_id=str(job.case_id),
                        target_id=str(job.target_id),
                        job_id=str(job.id),
                    ),
                )
                resp = await inference_client.run(req)
                if resp.enabled:
                    inference_summary = resp.output
            except Exception:
                logger.debug("Inference hook skipped for comments", exc_info=True)

        return ProfilerArtifact(
            org_id=job.org_id,
            case_id=job.case_id,
            target_id=job.target_id,
            job_id=job.id,
            artifact_type="comments_summary",
            version="v1",
            payload={
                "total_comments": len(comments),
                "top_bigrams": bigrams,
                "top_trigrams": trigrams,
                "inference_summary": inference_summary,
            },
        )

    def _top_ngrams(self, text: str, n: int = 2, top_k: int = 20) -> list[dict]:
        words = re.findall(r"\b\w{2,}\b", text.lower())
        if len(words) < n:
            return []
        grams = [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
        return [
            {"phrase": phrase, "count": count}
            for phrase, count in Counter(grams).most_common(top_k)
        ]
