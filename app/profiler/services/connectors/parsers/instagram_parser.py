"""Instagram HTML parser - v1 minimal extraction."""

from __future__ import annotations

import hashlib
import logging
import re
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

SOURCE = "instagram"


class InstagramParser:
    """Extract canonical entities from Instagram HTML."""

    def parse(self, html: str, url: str) -> ParseResult:
        result = ParseResult()
        og = extract_og_meta(html)
        json_ld = extract_json_ld(html)
        username = self._extract_username(url)

        if og.get("title") or username:
            result.profiles.append(
                {
                    "source": SOURCE,
                    "source_id": username,
                    "username": username,
                    "display_name": og.get("title", username),
                    "bio": og.get("description", ""),
                }
            )

        caption = og.get("description", "")
        if caption:
            post_id = (
                self._extract_post_id(url)
                or hashlib.md5(
                    caption[:200].encode(), usedforsecurity=False
                ).hexdigest()[:16]
            )
            result.posts.append(
                {
                    "source": SOURCE,
                    "source_post_id": post_id,
                    "text_content": caption,
                    "engagement_counts": self._parse_engagement(caption),
                }
            )

            for tag in extract_hashtags(caption):
                result.tags.append({"source": SOURCE, "tag": tag, "post_id": post_id})

            for mention in extract_mentions(caption):
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
            loc = ld.get("contentLocation") or ld.get("location")
            if isinstance(loc, dict) and loc.get("name"):
                result.locations.append(
                    {
                        "source": SOURCE,
                        "location_name": loc["name"],
                    }
                )

        logger.debug(
            "Instagram parse complete",
            extra={"url": url[:80], "posts": len(result.posts)},
        )
        return result

    def _extract_username(self, url: str) -> str:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        return parts[0] if parts and parts[0] != "p" else ""

    def _extract_post_id(self, url: str) -> str:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "p":
            return parts[1]
        return ""

    def _parse_engagement(self, text: str) -> dict:
        counts: dict[str, int] = {}
        likes_match = re.search(r"([\d,]+)\s+likes?", text, re.IGNORECASE)
        if likes_match:
            counts["likes"] = int(likes_match.group(1).replace(",", ""))
        comments_match = re.search(r"([\d,]+)\s+comments?", text, re.IGNORECASE)
        if comments_match:
            counts["comments"] = int(comments_match.group(1).replace(",", ""))
        return counts
