"""Normalizer - produces canonical entities from source documents."""

from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from app.profiler.models.entities.comment_entity import CommentEntity
from app.profiler.models.entities.interaction_entity import InteractionEntity
from app.profiler.models.entities.location_entity import LocationEntity
from app.profiler.models.entities.media_entity import MediaEntity
from app.profiler.models.entities.post_entity import PostEntity
from app.profiler.models.entities.profile_entity import ProfileEntity
from app.profiler.models.entities.review_entity import ReviewEntity
from app.profiler.models.entities.tag_entity import TagEntity
from app.profiler.models.job import ProfilerJob
from app.profiler.models.source_document import ProfilerSourceDocument
from app.profiler.services.connectors.parsers import ParseResult
from app.profiler.services.connectors.parsers.facebook_parser import FacebookParser
from app.profiler.services.connectors.parsers.google_parser import GoogleParser
from app.profiler.services.connectors.parsers.instagram_parser import InstagramParser
from app.profiler.services.connectors.parsers.x_parser import XParser
from app.profiler.services.evidence_store import AzureBlobEvidenceStore
from app.profiler.utils.now import utc_now
from app.profiler.utils.url_detect import detect_source_by_hostname

logger = logging.getLogger(__name__)

_PARSERS: dict[str, type] = {
    "facebook": FacebookParser,
    "x": XParser,
    "instagram": InstagramParser,
    "google": GoogleParser,
}


class NormalizerService:
    """Normalize source documents to canonical entities."""

    def __init__(self) -> None:
        self._evidence_store = AzureBlobEvidenceStore()

    # ---- admin/testing: normalize from blob without Redis/worker ----

    async def normalize_from_blob(
        self,
        blob_path: str,
        url: str,
        org_id: ObjectId,
        case_id: ObjectId,
        target_id: ObjectId,
        source: str | None = None,
    ) -> int:
        """
        Load JSON from blob and run normalization synchronously.
        For admin/testing - no Redis, no jobs. Returns entities created count.
        """
        src = source or detect_source_by_hostname(url)
        doc = ProfilerSourceDocument.model_construct(
            id=ObjectId(),
            org_id=org_id,
            case_id=case_id,
            target_id=target_id,
            job_id=ObjectId(),
            url=url,
            captured_at=utc_now(),
            http_status=200,
            headers={},
            content_type="application/json",
            fetch_method="scrape",
            sha256="",
            blob_path=blob_path,
            parser_version="v1",
        )
        job = ProfilerJob.model_construct(
            id=ObjectId(),
            org_id=org_id,
            case_id=case_id,
            target_id=target_id,
            created_by=org_id,
            job_type="normalize",
            status="queued",
        )
        return await self._normalize_json_document(doc, job, src)

    # ---- backward compat for ProfilerService.write_artifacts ----

    def to_timeline_item(self, doc: ProfilerSourceDocument) -> dict[str, Any]:
        """Produce a basic timeline item from source document."""
        captured_at = doc.captured_at
        ts = captured_at.isoformat().replace("+00:00", "Z") if captured_at else ""
        return {
            "url": doc.url,
            "captured_at": ts,
            "sha256": doc.sha256,
            "source_document_id": str(doc.id),
        }

    # ---- full normalization flow ----

    async def normalize_job(self, job: ProfilerJob) -> int:
        """
        Run normalization for a capture job.
        Returns total number of entities created.
        """
        capture_job_id = (job.payload or {}).get("capture_job_id")
        if not capture_job_id:
            logger.warning(
                "Normalize job missing capture_job_id",
                extra={"job_id": str(job.id)},
            )
            return 0

        docs = await ProfilerSourceDocument.find(
            ProfilerSourceDocument.job_id == capture_job_id,
        ).to_list()

        if not docs:
            logger.info(
                "No source documents for capture job",
                extra={"capture_job_id": capture_job_id},
            )
            return 0

        total = 0
        for doc in docs:
            try:
                count = await self._normalize_document(doc, job)
                total += count
            except Exception:
                logger.exception(
                    "Failed to normalize document",
                    extra={"doc_id": str(doc.id), "job_id": str(job.id)},
                )
        return total

    async def _normalize_document(
        self, doc: ProfilerSourceDocument, job: ProfilerJob
    ) -> int:
        """Parse a single source document and create canonical entities."""
        source = detect_source_by_hostname(doc.url)

        if doc.fetch_method == "scrape" or doc.content_type == "application/json":
            return await self._normalize_json_document(doc, job, source)

        html = await self._evidence_store.get_text(doc.blob_path)
        parser_cls = _PARSERS.get(source)
        if not parser_cls:
            logger.info(
                "No parser for source",
                extra={"source": source, "url": doc.url[:80]},
            )
            return 0

        parser = parser_cls()
        parsed: ParseResult = parser.parse(html, doc.url)
        evidence_id = str(doc.id)
        now = utc_now()
        count = 0

        ctx: dict[str, Any] = {
            "org_id": doc.org_id,
            "case_id": doc.case_id,
            "target_id": doc.target_id,
        }

        # --- Profiles ---
        for p in parsed.profiles:
            existing = await ProfileEntity.find_one(
                ProfileEntity.source == p["source"],
                ProfileEntity.source_id == p["source_id"],
                ProfileEntity.target_id == doc.target_id,
            )
            if existing:
                existing.last_seen_at = now
                existing.display_name = p.get("display_name", existing.display_name)
                existing.bio = p.get("bio", existing.bio)
                await existing.save()
            else:
                await ProfileEntity(
                    **ctx,
                    source=p["source"],
                    source_id=p["source_id"],
                    username=p.get("username", ""),
                    display_name=p.get("display_name", ""),
                    bio=p.get("bio", ""),
                    first_seen_at=now,
                    last_seen_at=now,
                ).insert()
                count += 1

        author_profile = await ProfileEntity.find_one(
            ProfileEntity.target_id == doc.target_id,
            ProfileEntity.source == source,
        )
        author_pid = str(author_profile.id) if author_profile else ""

        # --- Posts + Tags ---
        for p in parsed.posts:
            src_post_id = p.get("source_post_id", "")
            existing = await PostEntity.find_one(
                PostEntity.source == p["source"],
                PostEntity.source_post_id == src_post_id,
                PostEntity.target_id == doc.target_id,
            )
            if not existing:
                post = await PostEntity(
                    **ctx,
                    source=p["source"],
                    source_post_id=src_post_id,
                    author_profile_id=author_pid,
                    text_content=p.get("text_content"),
                    engagement_counts=p.get("engagement_counts", {}),
                    evidence_id=evidence_id,
                ).insert()
                count += 1

                for t in parsed.tags:
                    if t.get("post_id") == src_post_id:
                        await TagEntity(
                            **ctx,
                            source=t["source"],
                            tag=t["tag"],
                            post_id=str(post.id),
                        ).insert()
                        count += 1

        # --- Comments ---
        for c in parsed.comments:
            src_cid = c.get("source_comment_id", "")
            existing = await CommentEntity.find_one(
                CommentEntity.source == c["source"],
                CommentEntity.source_comment_id == src_cid,
                CommentEntity.target_id == doc.target_id,
            )
            if not existing:
                await CommentEntity(
                    **ctx,
                    source=c["source"],
                    source_comment_id=src_cid,
                    parent_post_id=c.get("parent_post_id", ""),
                    author_profile_id=author_pid,
                    text=c.get("text", ""),
                    evidence_id=evidence_id,
                ).insert()
                count += 1

        # --- Media ---
        for m in parsed.media:
            src_mid = m.get("source_media_id", "")
            existing = await MediaEntity.find_one(
                MediaEntity.source == m["source"],
                MediaEntity.source_media_id == src_mid,
                MediaEntity.target_id == doc.target_id,
            )
            if not existing:
                await MediaEntity(
                    **ctx,
                    source=m["source"],
                    source_media_id=src_mid,
                    media_type=m.get("media_type", "image"),
                    blob_path=m.get("url", ""),
                    sha256="",
                    evidence_id=evidence_id,
                ).insert()
                count += 1

        # --- Locations ---
        for loc in parsed.locations:
            name = loc.get("location_name", "")
            if not name:
                continue
            existing = await LocationEntity.find_one(
                LocationEntity.location_name == name,
                LocationEntity.target_id == doc.target_id,
                LocationEntity.source == loc.get("source", source),
            )
            if existing:
                existing.last_seen_at = now
                if evidence_id not in existing.evidence_ids:
                    existing.evidence_ids.append(evidence_id)
                await existing.save()
            else:
                await LocationEntity(
                    **ctx,
                    source=loc.get("source", source),
                    location_name=name,
                    lat=loc.get("lat"),
                    lng=loc.get("lng"),
                    country_code=loc.get("country_code"),
                    first_seen_at=now,
                    last_seen_at=now,
                    evidence_ids=[evidence_id],
                ).insert()
                count += 1

        # --- Interactions (from mentions) ---
        for ix in parsed.interactions:
            counterparty_username = ix.get("counterparty_username", "")
            counterparty = await ProfileEntity.find_one(
                ProfileEntity.username == counterparty_username,
                ProfileEntity.target_id == doc.target_id,
            )
            cpid = str(counterparty.id) if counterparty else counterparty_username
            await InteractionEntity(
                **ctx,
                source=ix.get("source", source),
                actor_profile_id=author_pid,
                counterparty_profile_id=cpid,
                interaction_type=ix.get("interaction_type", "mention"),
                evidence_id=evidence_id,
            ).insert()
            count += 1

        # --- Reviews ---
        for rev in parsed.reviews:
            await ReviewEntity(
                **ctx,
                place_name=rev.get("place_name", ""),
                category=rev.get("category", ""),
                rating=rev.get("rating"),
                price_range=rev.get("price_range"),
                review_text=rev.get("review_text", ""),
                evidence_id=evidence_id,
            ).insert()
            count += 1

        logger.info(
            "Document normalized",
            extra={
                "doc_id": str(doc.id),
                "source": source,
                "entities_created": count,
            },
        )
        return count

    async def _normalize_json_document(
        self,
        doc: ProfilerSourceDocument,
        job: ProfilerJob,
        source: str,
    ) -> int:
        """Map ExtractedProfile JSON to canonical entities."""
        data = await self._evidence_store.get_json(doc.blob_path)
        evidence_id = str(doc.id)
        now = utc_now()
        count = 0

        ctx: dict[str, Any] = {
            "org_id": doc.org_id,
            "case_id": doc.case_id,
            "target_id": doc.target_id,
        }

        identity = data.get("identity", {})
        handle = identity.get("handle", "") or identity.get("display_name", "")
        if handle or identity.get("display_name"):
            existing = await ProfileEntity.find_one(
                ProfileEntity.source == source,
                ProfileEntity.source_id == handle,
                ProfileEntity.target_id == doc.target_id,
            )
            if existing:
                existing.last_seen_at = now
                existing.display_name = identity.get(
                    "display_name", existing.display_name
                )
                existing.bio = identity.get("bio", existing.bio)
                await existing.save()
            else:
                await ProfileEntity(
                    **ctx,
                    source=source,
                    source_id=handle or "unknown",
                    username=handle,
                    display_name=identity.get("display_name", ""),
                    bio=identity.get("bio", ""),
                    first_seen_at=now,
                    last_seen_at=now,
                ).insert()
                count += 1

        author_profile = await ProfileEntity.find_one(
            ProfileEntity.target_id == doc.target_id,
            ProfileEntity.source == source,
        )
        author_pid = str(author_profile.id) if author_profile else ""

        content = data.get("content", {})
        for po in content.get("posts", []):
            src_post_id = po.get("id", "")
            if not src_post_id:
                continue
            existing = await PostEntity.find_one(
                PostEntity.source == source,
                PostEntity.source_post_id == src_post_id,
                PostEntity.target_id == doc.target_id,
            )
            if not existing:
                post = await PostEntity(
                    **ctx,
                    source=source,
                    source_post_id=src_post_id,
                    author_profile_id=author_pid,
                    text_content=po.get("text", ""),
                    engagement_counts={},
                    evidence_id=evidence_id,
                ).insert()
                count += 1
                for tag in po.get("hashtags", []):
                    await TagEntity(
                        **ctx,
                        source=source,
                        tag=tag,
                        post_id=str(post.id),
                    ).insert()
                    count += 1

        for c in content.get("comments", []):
            src_cid = c.get("id", "")
            if not src_cid:
                continue
            existing = await CommentEntity.find_one(
                CommentEntity.source == source,
                CommentEntity.source_comment_id == src_cid,
                CommentEntity.target_id == doc.target_id,
            )
            if not existing:
                await CommentEntity(
                    **ctx,
                    source=source,
                    source_comment_id=src_cid,
                    parent_post_id=c.get("parent_post_id", ""),
                    author_profile_id=author_pid,
                    text=c.get("text", ""),
                    evidence_id=evidence_id,
                ).insert()
                count += 1

        for loc in data.get("locations", []):
            name = loc.get("place_name", "")
            if not name:
                continue
            existing = await LocationEntity.find_one(
                LocationEntity.location_name == name,
                LocationEntity.target_id == doc.target_id,
                LocationEntity.source == source,
            )
            if existing:
                existing.last_seen_at = now
                if evidence_id not in existing.evidence_ids:
                    existing.evidence_ids.append(evidence_id)
                await existing.save()
            else:
                await LocationEntity(
                    **ctx,
                    source=source,
                    location_name=name,
                    lat=loc.get("lat"),
                    lng=loc.get("lng"),
                    country_code=loc.get("country_code"),
                    first_seen_at=now,
                    last_seen_at=now,
                    evidence_ids=[evidence_id],
                ).insert()
                count += 1

        for ix in data.get("interactions", []):
            counterparty = ix.get("counterparty_handle", "")
            cpid = counterparty
            cp = await ProfileEntity.find_one(
                ProfileEntity.username == counterparty,
                ProfileEntity.target_id == doc.target_id,
            )
            if cp:
                cpid = str(cp.id)
            await InteractionEntity(
                **ctx,
                source=source,
                actor_profile_id=author_pid,
                counterparty_profile_id=cpid,
                interaction_type=ix.get("type", "mention"),
                evidence_id=evidence_id,
            ).insert()
            count += 1

        for rev in data.get("reviews", []):
            await ReviewEntity(
                **ctx,
                place_name=rev.get("place_name", ""),
                category=rev.get("category", ""),
                rating=rev.get("rating"),
                price_range=rev.get("price_range"),
                review_text=rev.get("review_text", ""),
                evidence_id=evidence_id,
            ).insert()
            count += 1

        logger.info(
            "JSON document normalized",
            extra={
                "doc_id": str(doc.id),
                "source": source,
                "entities_created": count,
            },
        )
        return count
