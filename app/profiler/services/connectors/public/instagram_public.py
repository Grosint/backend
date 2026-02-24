"""Instagram public connector - Playwright scrape with GraphQL/DOM extraction."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import re
from typing import Any

from app.profiler.services.connectors.base import ConnectorResult, ScraperResult
from app.profiler.services.connectors.parsers import (
    ParseResult,
    extract_hashtags,
    extract_mentions,
    parse_result_to_extracted_profile,
)
from app.profiler.services.connectors.playwright_helpers import run_playwright_session
from app.profiler.utils.gating import is_login_wall
from app.profiler.utils.now import utc_now
from app.profiler.utils.url_detect import normalize_canonical_url

logger = logging.getLogger(__name__)

SOURCE = "instagram"

_INSTAGRAM_API_PATTERNS = [
    "/graphql/query/",
    "/api/graphql",
    "/query/",
    "/api/v1/users/",
    "/api/v1/feed/",
]


def _normalize_instagram_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if "instagram.com/" in url:
        m = re.search(r"instagram\.com/([^/?]+)", url)
        if m:
            return f"https://www.instagram.com/{m.group(1)}/"
    if not url.startswith("http"):
        return f"https://www.instagram.com/{url}/"
    return url


def _parse_post_node(node: dict[str, Any]) -> dict[str, Any] | None:
    if not node or not node.get("shortcode"):
        return None
    post: dict[str, Any] = {
        "id": node.get("id"),
        "shortcode": node.get("shortcode"),
        "url": (
            f"https://www.instagram.com/p/{node.get('shortcode')}/"
            if node.get("shortcode")
            else None
        ),
        "timestamp": node.get("taken_at_timestamp"),
        "is_video": node.get("is_video", False),
    }
    edges = node.get("edge_media_to_caption", {}).get("edges", [])
    post["caption"] = edges[0]["node"]["text"] if edges else node.get("caption", "")
    like_edges = node.get("edge_media_preview_like", {})
    post["likes_count"] = like_edges.get("count", 0) or node.get("likes", {}).get(
        "count", 0
    )
    post["comments_count"] = node.get("edge_media_to_comment", {}).get("count", 0)
    post["display_url"] = node.get("display_url") or node.get("display_src")
    comments = []
    for ce in (node.get("edge_media_to_comment", {}).get("edges") or [])[:50]:
        cn = ce.get("node", {})
        owner = cn.get("owner", {})
        comments.append(
            {
                "id": cn.get("id"),
                "text": cn.get("text", ""),
                "author": {"username": owner.get("username", "")},
                "timestamp": cn.get("created_at"),
            }
        )
    post["comments"] = comments
    return post


def _find_posts_in_graphql(obj: Any, depth: int = 0) -> list[dict]:
    if depth > 10:
        return []
    found = []
    if isinstance(obj, dict):
        if "edge_owner_to_timeline_media" in obj:
            for edge in obj["edge_owner_to_timeline_media"].get("edges", []):
                p = _parse_post_node(edge.get("node", {}))
                if p:
                    found.append(p)
        if "user" in obj and isinstance(obj["user"], dict):
            found.extend(_find_posts_in_graphql(obj["user"], depth + 1))
        for v in obj.values():
            found.extend(_find_posts_in_graphql(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_posts_in_graphql(item, depth + 1))
    return found


def _dedupe_posts(posts: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for p in posts:
        key = p.get("shortcode") or p.get("id")
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


async def _extract_instagram(page, api_responses: list[dict]) -> dict[str, Any]:
    posts = []

    # From GraphQL/API responses
    for r in api_responses:
        with contextlib.suppress(Exception):
            data = r.get("data", r)
            posts.extend(_find_posts_in_graphql(data))

    # From page JS (window._sharedData)
    try:
        posts_js = await page.evaluate(
            """
            () => {
                const posts = [];
                try {
                    if (window._sharedData && window._sharedData.entry_data) {
                        const ep = window._sharedData.entry_data;
                        if (ep.ProfilePage && ep.ProfilePage[0]) {
                            const pp = ep.ProfilePage[0];
                            if (pp.graphql && pp.graphql.user) {
                                const u = pp.graphql.user;
                                const edges = (u.edge_owner_to_timeline_media || {}).edges || [];
                                edges.forEach(edge => {
                                    const n = edge.node || {};
                                    if (n.shortcode) {
                                        posts.push({
                                            shortcode: n.shortcode,
                                            caption: (n.edge_media_to_caption?.edges?.[0]?.node?.text) || '',
                                            likes_count: n.edge_media_preview_like?.count || n.likes?.count || 0,
                                            comments_count: n.edge_media_to_comment?.count || 0,
                                            display_url: n.display_url || n.display_src,
                                            url: 'https://www.instagram.com/p/' + n.shortcode + '/'
                                        });
                                    }
                                });
                            }
                        }
                    }
                } catch (e) {}
                return posts;
            }
            """
        )
        for p in posts_js:
            if (
                p
                and p.get("shortcode")
                and not any(x.get("shortcode") == p["shortcode"] for x in posts)
            ):
                posts.append(p)
    except Exception as e:
        logger.debug("Instagram JS extract: %s", e)

    # From DOM
    try:
        dom_posts = await page.evaluate(
            """
            () => {
                const posts = [];
                document.querySelectorAll('article').forEach((art, i) => {
                    if (i < 12) {
                        art.querySelectorAll('a[href*="/p/"]').forEach(link => {
                            const h = link.getAttribute('href') || '';
                            const m = h.match(/\\/p\\/([^\\/]+)/);
                            if (m && !posts.find(p => p.shortcode === m[1])) {
                                posts.push({ shortcode: m[1], url: 'https://www.instagram.com' + h });
                            }
                        });
                    }
                });
                return posts;
            }
            """
        )
        for p in dom_posts:
            if (
                p
                and p.get("shortcode")
                and not any(x.get("shortcode") == p["shortcode"] for x in posts)
            ):
                posts.append(p)
    except Exception as e:
        logger.debug("Instagram DOM extract: %s", e)

    unique_posts = _dedupe_posts(posts)

    # Profile from sharedData
    profile_info: dict[str, Any] = {}
    try:
        shared = await page.evaluate(
            """
            () => {
                try {
                    if (window._sharedData && window._sharedData.entry_data?.ProfilePage?.[0]?.graphql?.user) {
                        return window._sharedData.entry_data.ProfilePage[0].graphql.user;
                    }
                } catch (e) {}
                return null;
            }
            """
        )
        if shared:
            profile_info = {
                "username": shared.get("username"),
                "full_name": shared.get("full_name"),
                "biography": shared.get("biography"),
                "followers": shared.get("edge_followed_by", {}).get("count"),
                "following": shared.get("edge_follow", {}).get("count"),
                "posts_count": shared.get("edge_owner_to_timeline_media", {}).get(
                    "count"
                ),
                "is_verified": shared.get("is_verified"),
                "profile_pic_url": shared.get("profile_pic_url_hd")
                or shared.get("profile_pic_url"),
            }
    except Exception as e:
        logger.debug("Instagram profile extract: %s", e)

    return {
        "profile_info": profile_info,
        "posts": unique_posts,
    }


def _scraped_to_parse_result(
    url: str, html: str, scraped: dict[str, Any]
) -> ParseResult:
    result = ParseResult()
    profile_info = scraped.get("profile_info", {})
    posts = scraped.get("posts", [])

    username = profile_info.get("username", "")
    if not username:
        from urllib.parse import urlparse

        parts = urlparse(url).path.strip("/").split("/")
        username = parts[0] if parts and parts[0] != "p" else ""

    if username or profile_info.get("full_name"):
        result.profiles.append(
            {
                "source": SOURCE,
                "source_id": username,
                "username": username,
                "display_name": profile_info.get("full_name", username),
                "bio": profile_info.get("biography", ""),
                "followers_count": profile_info.get("followers"),
                "following_count": profile_info.get("following"),
            }
        )

    for po in posts:
        pid = po.get("shortcode", "") or po.get("id", "") or ""
        if not pid:
            pid = hashlib.md5(
                (po.get("caption", "") or "")[:200].encode(), usedforsecurity=False
            ).hexdigest()[:16]
        text = po.get("caption", "") or po.get("text", "") or ""
        result.posts.append(
            {
                "source": SOURCE,
                "source_post_id": pid,
                "text_content": text,
                "engagement_counts": {
                    "likes": po.get("likes_count", 0),
                    "comments": po.get("comments_count", 0),
                },
            }
        )
        for tag in extract_hashtags(text):
            result.tags.append({"source": SOURCE, "tag": tag, "post_id": pid})
        for mention in extract_mentions(text):
            result.interactions.append(
                {
                    "source": SOURCE,
                    "counterparty_username": mention,
                    "interaction_type": "mention",
                }
            )
        if po.get("display_url"):
            mid = hashlib.md5(
                po["display_url"].encode(), usedforsecurity=False
            ).hexdigest()[:16]
            result.media.append(
                {
                    "source": SOURCE,
                    "source_media_id": mid,
                    "media_type": "image",
                    "url": po["display_url"],
                }
            )
        for c in po.get("comments", []):
            result.comments.append(
                {
                    "source": SOURCE,
                    "source_comment_id": c.get("id", ""),
                    "text": c.get("text", ""),
                    "parent_post_id": pid,
                    "author_handle": (c.get("author") or {}).get("username", ""),
                }
            )

    if profile_info.get("profile_pic_url"):
        mid = hashlib.md5(
            profile_info["profile_pic_url"].encode(), usedforsecurity=False
        ).hexdigest()[:16]
        result.media.insert(
            0,
            {
                "source": SOURCE,
                "source_media_id": mid,
                "media_type": "image",
                "url": profile_info["profile_pic_url"],
            },
        )

    return result


class InstagramPublicConnector:
    """Instagram public - Playwright scrape with GraphQL/JS/DOM extraction."""

    def resolve(self, input_value: str, target_type: str) -> ConnectorResult:
        url = self._to_url(input_value, target_type)
        return ConnectorResult(
            detected_source="instagram",
            canonical_url=normalize_canonical_url(url),
        )

    def _to_url(self, input_value: str, target_type: str) -> str:
        if target_type == "url":
            return _normalize_instagram_url(input_value)
        return f"https://www.instagram.com/{input_value.lstrip('@')}/"

    async def fetch_and_parse(self, url: str) -> ScraperResult:
        url = _normalize_instagram_url(url)
        try:
            body, status, headers, scraped = await run_playwright_session(
                url,
                _extract_instagram,
                api_url_patterns=_INSTAGRAM_API_PATTERNS,
            )

            if status in (401, 403):
                return ScraperResult(
                    status="not_collectible",
                    reason=f"HTTP {status} - auth required",
                )

            if is_login_wall(body):
                return ScraperResult(
                    status="not_collectible",
                    reason="Login/sign-in wall detected",
                )

            html = body.decode("utf-8", errors="replace")
            parse_result = _scraped_to_parse_result(url, html, scraped)

            # Fallback: if no profile/posts from JS, use OG meta from HTML
            if not parse_result.profiles and not parse_result.posts:
                from app.profiler.services.connectors.parsers import extract_og_meta

                og = extract_og_meta(html)
                if og.get("title"):
                    parse_result.profiles.append(
                        {
                            "source": SOURCE,
                            "source_id": url.split("/")[-2] if "/" in url else "",
                            "username": url.split("/")[-2] if "/" in url else "",
                            "display_name": og.get("title", ""),
                            "bio": og.get("description", ""),
                        }
                    )
                if og.get("description"):
                    parse_result.posts.append(
                        {
                            "source": SOURCE,
                            "source_post_id": hashlib.md5(
                                og["description"][:200].encode(),
                                usedforsecurity=False,
                            ).hexdigest()[:16],
                            "text_content": og["description"],
                            "engagement_counts": {},
                        }
                    )

            now = utc_now()
            provenance = {
                "raw_url": url,
                "capture_timestamp": now.isoformat().replace("+00:00", "Z"),
                "http_status": status,
                "headers": headers,
                "sha256": "",
                "blob_path": "",
                "parser_version": "v1",
            }
            extracted = parse_result_to_extracted_profile(parse_result, url, provenance)
            return ScraperResult(status="collected", extracted=extracted)

        except Exception as e:
            logger.exception(
                "Instagram fetch_and_parse failed",
                extra={"url": url[:80], "error": str(e)},
            )
            return ScraperResult(status="not_collectible", reason=str(e))
