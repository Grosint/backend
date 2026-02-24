"""X (Twitter) HTML parser - v1 minimal extraction."""

from __future__ import annotations

import hashlib
import logging
from urllib.parse import urlparse

from app.profiler.services.connectors.parsers import (
    ParseResult,
    extract_hashtags,
    extract_image_urls,
    extract_mentions,
    extract_og_meta,
)

logger = logging.getLogger(__name__)

SOURCE = "x"


class XParser:
    """Extract canonical entities from X/Twitter HTML."""

    def parse(self, html: str, url: str) -> ParseResult:
        result = ParseResult()
        og = extract_og_meta(html)

        if og.get("title"):
            username = self._extract_username(url, og.get("title", ""))
            result.profiles.append(
                {
                    "source": SOURCE,
                    "source_id": username,
                    "username": username,
                    "display_name": og.get("title", ""),
                    "bio": og.get("description", ""),
                }
            )

        post_text = og.get("description", "")
        if post_text:
            post_id = (
                self._extract_tweet_id(url)
                or hashlib.md5(
                    post_text[:200].encode(), usedforsecurity=False
                ).hexdigest()[:16]
            )
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

        logger.debug(
            "X parse complete", extra={"url": url[:80], "posts": len(result.posts)}
        )
        return result

    def _extract_username(self, url: str, title: str) -> str:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        if parts:
            return parts[0].lstrip("@")
        if "(@" in title:
            start = title.index("(@") + 2
            end = title.index(")", start)
            return title[start:end]
        return title

    def _extract_tweet_id(self, url: str) -> str:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 3 and parts[1] == "status":
            return parts[2]
        return ""
