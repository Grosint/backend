"""Facebook HTML parser - v1 minimal extraction."""

from __future__ import annotations

import hashlib
import logging
from urllib.parse import urlparse

from app.profiler.services.connectors.parsers import (
    ParseResult,
    extract_hashtags,
    extract_image_urls,
    extract_json_ld,
    extract_mentions,
    extract_og_meta,
)

logger = logging.getLogger(__name__)

SOURCE = "facebook"


class FacebookParser:
    """Extract canonical entities from Facebook HTML."""

    def parse(self, html: str, url: str) -> ParseResult:
        result = ParseResult()
        og = extract_og_meta(html)
        json_ld = extract_json_ld(html)

        if og.get("title"):
            result.profiles.append(
                {
                    "source": SOURCE,
                    "source_id": self._source_id(url),
                    "username": og.get("title", ""),
                    "display_name": og.get("title", ""),
                    "bio": og.get("description", ""),
                }
            )

        post_text = og.get("description", "")
        if post_text:
            post_id = hashlib.md5(
                post_text[:200].encode(), usedforsecurity=False
            ).hexdigest()[:16]
            result.posts.append(
                {
                    "source": SOURCE,
                    "source_post_id": post_id,
                    "text_content": post_text,
                    "engagement_counts": {},
                }
            )

            for tag in extract_hashtags(post_text):
                result.tags.append({"source": SOURCE, "tag": tag, "post_id": post_id})

            for mention in extract_mentions(post_text):
                result.interactions.append(
                    {
                        "source": SOURCE,
                        "counterparty_username": mention,
                        "interaction_type": "mention",
                    }
                )

        for img_url in extract_image_urls(html):
            mid = hashlib.md5(img_url.encode(), usedforsecurity=False).hexdigest()[:16]
            result.media.append(
                {
                    "source": SOURCE,
                    "source_media_id": mid,
                    "media_type": "image",
                    "url": img_url,
                }
            )

        for ld in json_ld:
            loc = ld.get("location") or ld.get("contentLocation")
            if isinstance(loc, dict) and loc.get("name"):
                result.locations.append(
                    {
                        "source": SOURCE,
                        "location_name": loc["name"],
                        "lat": None,
                        "lng": None,
                    }
                )

        logger.debug(
            "Facebook parse complete",
            extra={"url": url[:80], "posts": len(result.posts)},
        )
        return result

    def _source_id(self, url: str) -> str:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        return parts[0] if parts and parts[0] else url
