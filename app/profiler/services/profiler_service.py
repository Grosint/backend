"""Profiler service - orchestrates capture, artifacts, jobs."""

from __future__ import annotations

import contextlib
import logging

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.source_document import ProfilerSourceDocument
from app.profiler.services.evidence_store import AzureBlobEvidenceStore
from app.profiler.services.normalizer_service import NormalizerService

logger = logging.getLogger(__name__)


class ProfilerService:
    """Orchestrate profiler artifacts from source documents."""

    def __init__(self) -> None:
        self._normalizer = NormalizerService()
        self._evidence_store = AzureBlobEvidenceStore()

    async def write_artifacts(
        self,
        source_document: ProfilerSourceDocument,
    ) -> list[ProfilerArtifact]:
        """
        Write baseline artifacts from a single source document.
        Returns list of created artifacts.
        """
        doc = source_document
        doc_id_str = str(doc.id)
        evidence_ids = [doc_id_str]

        # coverage: {collectible: bool, reason}
        coverage = ProfilerArtifact(
            org_id=doc.org_id,
            case_id=doc.case_id,
            target_id=doc.target_id,
            job_id=doc.job_id,
            artifact_type="coverage",
            payload={"collectible": True, "reason": "public_capture_succeeded"},
            evidence_ids=evidence_ids,
        )
        await coverage.insert()

        # profile_card: base + optional identity fields from scraped JSON
        captured_at = (
            doc.captured_at.isoformat().replace("+00:00", "Z")
            if doc.captured_at
            else ""
        )
        payload: dict = {
            "source": doc.fetch_method or "http",
            "canonical_url": doc.url,
            "captured_at": captured_at,
            "http_status": doc.http_status,
        }
        if doc.fetch_method == "scrape":
            with contextlib.suppress(Exception):
                data = await self._evidence_store.get_json(doc.blob_path)
                identity = data.get("identity", {})
                if identity:
                    payload["handle"] = identity.get("handle", "")
                    payload["display_name"] = identity.get("display_name", "")
                    payload["followers_count"] = identity.get("followers_count")
                    payload["verified"] = identity.get("verified")

        profile_card = ProfilerArtifact(
            org_id=doc.org_id,
            case_id=doc.case_id,
            target_id=doc.target_id,
            job_id=doc.job_id,
            artifact_type="profile_card",
            payload=payload,
            evidence_ids=evidence_ids,
        )
        await profile_card.insert()

        # timeline: [{url, captured_at, sha256, source_document_id}]
        timeline_item = self._normalizer.to_timeline_item(doc)
        timeline = ProfilerArtifact(
            org_id=doc.org_id,
            case_id=doc.case_id,
            target_id=doc.target_id,
            job_id=doc.job_id,
            artifact_type="timeline",
            payload={"items": [timeline_item]},
            evidence_ids=evidence_ids,
        )
        await timeline.insert()

        return [coverage, profile_card, timeline]
