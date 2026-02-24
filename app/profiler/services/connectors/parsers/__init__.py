"""HTML parsers for source-specific content extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParseResult:
    """Normalized parsing result from any source parser."""

    profiles: list[dict[str, Any]] = field(default_factory=list)
    posts: list[dict[str, Any]] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)
    media: list[dict[str, Any]] = field(default_factory=list)
    locations: list[dict[str, Any]] = field(default_factory=list)
    interactions: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    tags: list[dict[str, Any]] = field(default_factory=list)


HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
MENTION_RE = re.compile(r"@(\w+)", re.UNICODE)
IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
OG_DESC_RE = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")


def extract_json_ld(html: str) -> list[dict]:
    """Extract all JSON-LD blocks from HTML."""
    results: list[dict] = []
    for match in JSON_LD_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
        except (json.JSONDecodeError, ValueError):
            continue
    return results


def extract_hashtags(text: str) -> list[str]:
    """Extract hashtags from text."""
    return HASHTAG_RE.findall(text)


def extract_mentions(text: str) -> list[str]:
    """Extract @mentions from text."""
    return MENTION_RE.findall(text)


def extract_image_urls(html: str) -> list[str]:
    """Extract image URLs from HTML img tags and og:image meta."""
    urls: set[str] = set()
    for match in IMG_SRC_RE.finditer(html):
        url = match.group(1)
        if url.startswith("http") and not url.endswith(".svg"):
            urls.add(url)
    for match in OG_IMAGE_RE.finditer(html):
        urls.add(match.group(1))
    return list(urls)


def extract_og_meta(html: str) -> dict[str, str]:
    """Extract Open Graph meta tags."""
    result: dict[str, str] = {}
    title = OG_TITLE_RE.search(html)
    if title:
        result["title"] = title.group(1)
    desc = OG_DESC_RE.search(html)
    if desc:
        result["description"] = desc.group(1)
    img = OG_IMAGE_RE.search(html)
    if img:
        result["image"] = img.group(1)
    return result


def strip_html_tags(html: str) -> str:
    """Remove HTML tags, returning plain text."""
    return HTML_TAG_RE.sub(" ", html).strip()


def parse_result_to_extracted_profile(
    parse_result: ParseResult,
    url: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert ParseResult to ExtractedProfile dict structure.
    Provenance must already contain raw_url, capture_timestamp, http_status, headers, sha256, blob_path, parser_version.
    """
    identity: dict[str, Any] = {
        "handle": "",
        "display_name": "",
        "bio": "",
        "profile_url": url,
        "profile_image_url": None,
        "followers_count": None,
        "following_count": None,
        "verified": None,
    }
    if parse_result.profiles:
        p = parse_result.profiles[0]
        identity["handle"] = p.get("username", "") or p.get("source_id", "")
        identity["display_name"] = p.get("display_name", "")
        identity["bio"] = p.get("bio", "")

    media_urls = [m.get("url", "") for m in parse_result.media if m.get("url")]
    if media_urls and not identity.get("profile_image_url"):
        identity["profile_image_url"] = media_urls[0]

    tags_by_post: dict[str, list[str]] = {}
    for t in parse_result.tags:
        pid = t.get("post_id", "")
        tag = t.get("tag", "")
        if pid and tag:
            tags_by_post.setdefault(pid, []).append(tag)

    posts: list[dict[str, Any]] = []
    for po in parse_result.posts:
        pid = po.get("source_post_id", "")
        text = po.get("text_content", "")
        hashtags = tags_by_post.get(pid, [])
        mentions = []
        for ix in parse_result.interactions:
            if ix.get("interaction_type") == "mention":
                mentions.append(ix.get("counterparty_username", ""))
        posts.append(
            {
                "id": pid,
                "url": url if "/status/" not in url and "/p/" not in url else url,
                "created_at": None,
                "text": text,
                "media_refs": media_urls[:5],
                "hashtags": hashtags,
                "mentions": mentions,
                "link_urls": [],
                "is_reply": None,
                "in_reply_to": None,
            }
        )

    comments: list[dict[str, Any]] = []
    for c in parse_result.comments:
        comments.append(
            {
                "id": c.get("source_comment_id", ""),
                "url": "",
                "created_at": None,
                "text": c.get("text", ""),
                "author_handle": "",
                "parent_post_id": c.get("parent_post_id", ""),
            }
        )

    interactions: list[dict[str, Any]] = []
    for ix in parse_result.interactions:
        interactions.append(
            {
                "timestamp": None,
                "counterparty_handle": ix.get("counterparty_username", ""),
                "type": ix.get("interaction_type", "mention"),
                "evidence_pointer": "",
            }
        )

    locations: list[dict[str, Any]] = []
    for loc in parse_result.locations:
        locations.append(
            {
                "place_name": loc.get("location_name", ""),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
                "timestamp": None,
                "country_code": loc.get("country_code"),
            }
        )

    reviews: list[dict[str, Any]] = []
    for r in parse_result.reviews:
        reviews.append(
            {
                "place_name": r.get("place_name", ""),
                "category": r.get("category", ""),
                "rating": r.get("rating"),
                "review_text": r.get("review_text", ""),
                "timestamp": None,
                "price_range": r.get("price_range"),
            }
        )

    return {
        "provenance": provenance,
        "identity": identity,
        "content": {"posts": posts, "comments": comments},
        "interactions": interactions,
        "locations": locations,
        "reviews": reviews,
    }
