"""Facebook public connector - Playwright scrape with API/DOM extraction."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import re
from typing import Any
from urllib.parse import urlparse as _urlparse

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

SOURCE = "facebook"

_FACEBOOK_API_PATTERNS = [
    "/graphql",
    "/api/graphql",
    "/api/graphqlbatch",
    "/feed",
    "/posts",
    "/profile",
    "/page_content",
    "/home.php",
    "/profile.php",
    "/timeline",
]


def _normalize_facebook_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if "facebook.com/" in url:
        m = re.search(r"facebook\.com/([^/?]+)", url)
        if m:
            uname = m.group(1).lstrip("@")
            if not uname.startswith("profile.php") and not uname.startswith("pages/"):
                return f"https://www.facebook.com/{uname}"
    if not url.startswith("http"):
        return f"https://www.facebook.com/{url.lstrip('@')}"
    return url


def _parse_post_node(node: dict[str, Any]) -> dict[str, Any] | None:
    if not node:
        return None
    has_post = any(
        k in node
        for k in ["message", "story", "post_id", "id", "created_time", "timestamp"]
    )
    if not has_post:
        return None
    likes = node.get("likes")
    like_count = 0
    if isinstance(likes, dict):
        like_count = (likes.get("summary") or {}).get("total_count", 0)
    elif isinstance(likes, (int, float)):
        like_count = int(likes)
    comments = node.get("comments")
    comment_count = 0
    if isinstance(comments, dict):
        comment_count = (comments.get("summary") or {}).get("total_count", 0)
    elif isinstance(comments, (int, float)):
        comment_count = int(comments)
    shares = node.get("shares", {})
    share_count = shares.get("count", 0) if isinstance(shares, dict) else (shares or 0)
    post = {
        "id": node.get("post_id") or node.get("id"),
        "text": node.get("message")
        or node.get("story")
        or node.get("description")
        or "",
        "created_time": node.get("created_time") or node.get("timestamp"),
        "likes": like_count,
        "comments": comment_count,
        "shares": share_count,
    }
    if "from" in node:
        f = node["from"]
        post["author"] = {
            "name": f.get("name"),
            "id": f.get("id"),
            "username": f.get("username"),
        }
    return post


def _find_posts_in_api(obj: Any, depth: int = 0) -> list[dict]:
    if depth > 15:
        return []
    found = []
    if isinstance(obj, dict):
        if "message" in obj or "story" in obj or "post_id" in obj:
            p = _parse_post_node(obj)
            if p:
                found.append(p)
        if "data" in obj:
            d = obj["data"]
            if isinstance(d, list):
                for item in d:
                    p = _parse_post_node(item)
                    if p:
                        found.append(p)
            elif isinstance(d, dict):
                for key in ["timeline", "feed", "posts", "edges", "nodes"]:
                    if key in d:
                        items = d[key]
                        if isinstance(items, list):
                            for item in items:
                                node = (
                                    item.get("node") if isinstance(item, dict) else item
                                )
                                p = (
                                    _parse_post_node(node)
                                    if isinstance(node, dict)
                                    else None
                                )
                                if p:
                                    found.append(p)
                        elif isinstance(items, dict):
                            found.extend(_find_posts_in_api(items, depth + 1))
        if "feed" in obj and isinstance(obj["feed"], dict) and "data" in obj["feed"]:
            for item in obj["feed"]["data"]:
                p = _parse_post_node(item)
                if p:
                    found.append(p)
        for v in obj.values():
            found.extend(_find_posts_in_api(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_posts_in_api(item, depth + 1))
    return found


def _dedupe_posts(posts: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for p in posts:
        key = p.get("id") or p.get("post_id")
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
        elif not key and p.get("text"):
            h = hash(p.get("text", "")[:100])
            if h not in seen:
                seen.add(h)
                unique.append(p)
    return unique


async def _extract_facebook(page, api_responses: list[dict]) -> dict[str, Any]:
    posts = []
    for r in api_responses:
        with contextlib.suppress(Exception):
            posts.extend(_find_posts_in_api(r))
    try:
        posts_js = await page.evaluate(
            """
            () => {
                const posts = [];
                try {
                    if (window.__d && Array.isArray(window.__d)) {
                        window.__d.forEach(item => {
                            if (item && (item.message || item.story || item.post_id)) {
                                posts.push({
                                    id: item.post_id || item.id,
                                    text: item.message || item.story || '',
                                    likes: item.likes || item.reaction_count || 0,
                                    comments: item.comments || item.comment_count || 0
                                });
                            }
                        });
                    }
                    if (window.__initialData__?.feed?.entries) {
                        window.__initialData__.feed.entries.forEach(entry => {
                            if (entry.message || entry.story) {
                                posts.push({
                                    id: entry.post_id || entry.id,
                                    text: entry.message || entry.story || '',
                                    likes: entry.likes || 0,
                                    comments: entry.comments || 0
                                });
                            }
                        });
                    }
                    const articles = document.querySelectorAll('[role="article"]');
                    articles.forEach((art, i) => {
                        if (i < 20) {
                            const textEl = art.querySelector('[data-testid="post_message"]') ||
                                art.querySelector('div[data-ad-preview="message"]');
                            const text = textEl ? textEl.innerText : '';
                            const id = art.getAttribute('data-pagelet') || art.getAttribute('data-ft') || '';
                            if (text || id) posts.push({ id, text, source: 'dom_js' });
                        }
                    });
                } catch (e) {}
                return posts;
            }
            """
        )
        for p in posts_js:
            if (
                p
                and (p.get("text") or p.get("id"))
                and not any(x.get("id") == p.get("id") and p.get("id") for x in posts)
            ):
                posts.append(p)
    except Exception as e:
        logger.debug("Facebook JS extract: %s", e)
    try:
        dom_posts = await page.evaluate(
            """
            () => {
                const posts = [];
                document.querySelectorAll('[role="article"]').forEach((art, i) => {
                    if (i < 20) {
                        const textEl = art.querySelector('[data-testid="post_message"]') ||
                            art.querySelector('div[data-ad-preview="message"]') ||
                            art.querySelector('[data-testid="story-subtitle"]');
                        const text = textEl ? textEl.innerText : '';
                        const id = art.getAttribute('data-pagelet') || art.getAttribute('data-ft') || '';
                        if (text || id) posts.push({ id, text, source: 'dom' });
                    }
                });
                return posts;
            }
            """
        )
        for p in dom_posts:
            if (
                p
                and (p.get("text") or p.get("id"))
                and not any(x.get("id") == p.get("id") and p.get("id") for x in posts)
            ):
                posts.append(p)
    except Exception as e:
        logger.debug("Facebook DOM extract: %s", e)
    unique_posts = _dedupe_posts(posts)
    profile_info: dict[str, Any] = {}
    try:
        page_data = await page.evaluate(
            """
            () => {
                const d = {};
                try {
                    if (window.__initialData__?.profile) {
                        d.profile = window.__initialData__.profile;
                    }
                } catch (e) {}
                return d;
            }
            """
        )
        if page_data.get("profile"):
            prof = page_data["profile"]
            profile_info = {
                "name": prof.get("name"),
                "username": prof.get("username"),
                "bio": prof.get("bio") or prof.get("about"),
                "followers_count": prof.get("followers_count"),
                "likes_count": prof.get("likes_count"),
                "verified": prof.get("verified", False),
            }
    except Exception as e:
        logger.debug("Facebook profile extract: %s", e)
    return {"profile_info": profile_info, "posts": unique_posts}


def _scraped_to_parse_result(
    url: str, html: str, scraped: dict[str, Any]
) -> ParseResult:
    result = ParseResult()
    profile_info = scraped.get("profile_info", {})
    posts = scraped.get("posts", [])
    parts = _urlparse(url).path.strip("/").split("/")
    username = profile_info.get("username") or (parts[0] if parts else "")
    if username or profile_info.get("name"):
        result.profiles.append(
            {
                "source": SOURCE,
                "source_id": username,
                "username": username,
                "display_name": profile_info.get("name", username),
                "bio": profile_info.get("bio", ""),
            }
        )
    for po in posts:
        pid = po.get("id", "") or ""
        text = po.get("text", "")
        if not pid and text:
            pid = hashlib.md5(text[:200].encode(), usedforsecurity=False).hexdigest()[
                :16
            ]
        result.posts.append(
            {
                "source": SOURCE,
                "source_post_id": pid,
                "text_content": text,
                "engagement_counts": {
                    "likes": po.get("likes", 0),
                    "comments": po.get("comments", 0),
                    "shares": po.get("shares", 0),
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
    return result


class FacebookPublicConnector:
    """Facebook public - Playwright scrape with API/JS/DOM extraction."""

    def resolve(self, input_value: str, target_type: str) -> ConnectorResult:
        url = self._to_url(input_value, target_type)
        return ConnectorResult(
            detected_source="facebook",
            canonical_url=normalize_canonical_url(url),
        )

    def _to_url(self, input_value: str, target_type: str) -> str:
        if target_type == "url":
            return _normalize_facebook_url(input_value)
        return f"https://www.facebook.com/{input_value.lstrip('@')}"

    async def fetch_and_parse(self, url: str) -> ScraperResult:
        url = _normalize_facebook_url(url)
        try:
            body, status, headers, scraped = await run_playwright_session(
                url,
                _extract_facebook,
                api_url_patterns=_FACEBOOK_API_PATTERNS,
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
            if not parse_result.profiles and not parse_result.posts:
                from app.profiler.services.connectors.parsers import extract_og_meta

                og = extract_og_meta(html)
                if og.get("title"):
                    _parts = _urlparse(url).path.strip("/").split("/")
                    parse_result.profiles.append(
                        {
                            "source": SOURCE,
                            "source_id": _parts[0] if _parts else "",
                            "username": og.get("title", ""),
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
                "Facebook fetch_and_parse failed",
                extra={"url": url[:80], "error": str(e)},
            )
            return ScraperResult(status="not_collectible", reason=str(e))
