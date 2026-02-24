"""Beliefs analyzer - topic bucketing from hashtags, no For/Against classification."""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.entities.post_entity import PostEntity
from app.profiler.models.entities.tag_entity import TagEntity

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "politics": [
        "politics",
        "election",
        "vote",
        "democracy",
        "government",
        "congress",
        "parliament",
        "liberal",
        "conservative",
    ],
    "religion": [
        "god",
        "church",
        "mosque",
        "temple",
        "prayer",
        "faith",
        "bible",
        "quran",
        "hindu",
        "christian",
        "muslim",
        "jewish",
    ],
    "sports": [
        "sports",
        "football",
        "soccer",
        "basketball",
        "cricket",
        "nfl",
        "nba",
        "fifa",
        "olympics",
        "baseball",
    ],
    "technology": [
        "tech",
        "ai",
        "crypto",
        "blockchain",
        "coding",
        "startup",
        "software",
        "programming",
        "data",
        "cloud",
    ],
    "lifestyle": [
        "fitness",
        "health",
        "travel",
        "food",
        "fashion",
        "beauty",
        "wellness",
        "yoga",
        "meditation",
    ],
    "activism": [
        "justice",
        "rights",
        "protest",
        "climate",
        "environment",
        "equality",
        "blm",
        "metoo",
        "activist",
    ],
}

QUOTE_RE = re.compile(r'["\u201c\u201d]([^"\u201c\u201d]{10,})["\u201c\u201d]')


class BeliefsAnalyzer:
    async def analyze(
        self,
        job: ProfilerJob,
        inference_client: InferenceClient,
    ) -> ProfilerArtifact | None:
        tags = await TagEntity.find(TagEntity.target_id == job.target_id).to_list()
        posts = await PostEntity.find(PostEntity.target_id == job.target_id).to_list()

        if not tags and not posts:
            return None

        topic_counts: Counter[str] = Counter()
        tag_to_topic: dict[str, str] = {}

        for t in tags:
            tag_lower = t.tag.lower()
            matched = False
            for topic, keywords in TOPIC_KEYWORDS.items():
                if any(kw in tag_lower for kw in keywords):
                    topic_counts[topic] += 1
                    tag_to_topic[t.tag] = topic
                    matched = True
                    break
            if not matched:
                topic_counts["other"] += 1
                tag_to_topic[t.tag] = "other"

        quotes: list[str] = []
        for p in posts:
            if p.text_content:
                found = QUOTE_RE.findall(p.text_content)
                quotes.extend(found[:5])

        return ProfilerArtifact(
            org_id=job.org_id,
            case_id=job.case_id,
            target_id=job.target_id,
            job_id=job.id,
            artifact_type="beliefs",
            version="v1",
            payload={
                "topic_distribution": dict(topic_counts.most_common()),
                "tag_topics": dict(list(tag_to_topic.items())[:50]),
                "quoted_statements": quotes[:20],
                "total_tags_analyzed": len(tags),
            },
        )
