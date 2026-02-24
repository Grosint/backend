"""Profiler analyzers - deterministic analysis of canonical entities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.services.analyzer.activity_analyzer import ActivityAnalyzer
from app.profiler.services.analyzer.beliefs_analyzer import BeliefsAnalyzer
from app.profiler.services.analyzer.comments_analyzer import CommentsAnalyzer
from app.profiler.services.analyzer.engagement_analyzer import EngagementAnalyzer
from app.profiler.services.analyzer.hashtags_analyzer import HashtagsAnalyzer
from app.profiler.services.analyzer.lifestyle_analyzer import LifestyleAnalyzer
from app.profiler.services.analyzer.locations_analyzer import LocationsAnalyzer
from app.profiler.services.analyzer.photos_analyzer import PhotosAnalyzer

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

ALL_ANALYZERS = [
    EngagementAnalyzer,
    HashtagsAnalyzer,
    LocationsAnalyzer,
    ActivityAnalyzer,
    CommentsAnalyzer,
    PhotosAnalyzer,
    LifestyleAnalyzer,
    BeliefsAnalyzer,
]


async def run_all_analyzers(
    job: ProfilerJob,
    inference_client: InferenceClient,
) -> list[ProfilerArtifact]:
    """Run every analyzer sequentially and return produced artifacts."""
    artifacts: list[ProfilerArtifact] = []
    for analyzer_cls in ALL_ANALYZERS:
        name = analyzer_cls.__name__
        try:
            analyzer = analyzer_cls()
            artifact = await analyzer.analyze(job, inference_client)
            if artifact:
                await artifact.insert()
                artifacts.append(artifact)
                logger.info(
                    "Analyzer produced artifact",
                    extra={"analyzer": name, "job_id": str(job.id)},
                )
        except Exception:
            logger.exception(
                "Analyzer failed",
                extra={"analyzer": name, "job_id": str(job.id)},
            )
    return artifacts
