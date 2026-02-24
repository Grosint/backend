"""Reddit public connector - Playwright scrape with DOM extraction."""

from __future__ import annotations

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

SOURCE = "reddit"


def _normalize_reddit_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if "reddit.com/user/" in url or "reddit.com/u/" in url:
        m = re.search(r"reddit\.com/(?:user|u)/([^/?]+)", url)
        if m:
            return f"https://www.reddit.com/user/{m.group(1)}"
    if not url.startswith("http"):
        return f"https://www.reddit.com/user/{url}"
    return url


async def _extract_reddit(page, api_responses: list) -> dict[str, Any]:
    profile_info: dict[str, Any] = {}
    try:
        profile_info = (
            await page.evaluate(
                """
            () => {
                const data = {};
                const usernameEl = document.querySelector('h1[class*="Username"]') ||
                    document.querySelector('h1') || document.querySelector('[class*="username"]');
                if (usernameEl) data.username = usernameEl.innerText.trim();
                const karmaEl = document.querySelector('[class*="Karma"]') ||
                    document.querySelector('[class*="karma"]');
                if (karmaEl) {
                    const m = karmaEl.innerText.trim().match(/[\\d,]+/);
                    if (m) data.karma = parseInt(m[0].replace(/,/g,'')) || 0;
                }
                return data;
            }
            """
            )
            or {}
        )
    except Exception as e:
        logger.debug("Reddit profile extract: %s", e)
    posts: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    try:
        posts = (
            await page.evaluate(
                """
            () => {
                const posts = [];
                const els = document.querySelectorAll('[data-testid="post-container"]') ||
                    document.querySelectorAll('[class*="Post"]');
                els.forEach((el, i) => {
                    if (i < 20) {
                        const titleEl = el.querySelector('h3') || el.querySelector('[class*="Title"]');
                        const textEl = el.querySelector('[class*="PostBody"]') ||
                            el.querySelector('[class*="post-body"]');
                        const title = titleEl ? titleEl.innerText.trim() : '';
                        const text = textEl ? textEl.innerText.trim() : '';
                        if (title || text) posts.push({
                            id: 'post_' + i,
                            title: title,
                            text: text
                        });
                    }
                });
                return posts;
            }
            """
            )
            or []
        )
    except Exception as e:
        logger.debug("Reddit posts extract: %s", e)
    try:
        comments = (
            await page.evaluate(
                """
            () => {
                const comments = [];
                const els = document.querySelectorAll('[data-testid="comment"]') ||
                    document.querySelectorAll('[class*="Comment"]');
                els.forEach((el, i) => {
                    if (i < 50) {
                        const textEl = el.querySelector('[class*="CommentBody"]') ||
                            el.querySelector('[class*="comment-body"]');
                        const text = textEl ? textEl.innerText.trim() : '';
                        if (text) comments.push({ id: 'comment_' + i, text: text });
                    }
                });
                return comments;
            }
            """
            )
            or []
        )
    except Exception as e:
        logger.debug("Reddit comments extract: %s", e)
    return {"profile_info": profile_info, "posts": posts, "comments": comments}


def _scraped_to_parse_result(
    url: str, html: str, scraped: dict[str, Any]
) -> ParseResult:
    result = ParseResult()
    profile_info = scraped.get("profile_info", {})
    posts = scraped.get("posts", [])
    comments = scraped.get("comments", [])
    from urllib.parse import urlparse

    parts = urlparse(url).path.strip("/").split("/")
    username = parts[-1] if parts and parts[-1] != "user" else ""
    if username or profile_info.get("username"):
        result.profiles.append(
            {
                "source": SOURCE,
                "source_id": username or profile_info.get("username", ""),
                "username": username or profile_info.get("username", ""),
                "display_name": profile_info.get("username", username),
                "bio": (
                    f"Karma: {profile_info.get('karma', '')}"
                    if profile_info.get("karma")
                    else ""
                ),
            }
        )
    for po in posts:
        pid = po.get("id", "") or ""
        text = (po.get("title", "") + " " + po.get("text", "")).strip()
        if not pid and text:
            pid = hashlib.md5(text[:200].encode(), usedforsecurity=False).hexdigest()[
                :16
            ]
        result.posts.append(
            {
                "source": SOURCE,
                "source_post_id": pid,
                "text_content": text,
                "engagement_counts": {},
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
    for c in comments:
        result.comments.append(
            {
                "source": SOURCE,
                "source_comment_id": c.get("id", ""),
                "text": c.get("text", ""),
                "parent_post_id": "",
                "author_handle": "",
            }
        )
    return result


class RedditPublicConnector:
    """Reddit public - Playwright scrape with DOM extraction."""

    def resolve(self, input_value: str, target_type: str) -> ConnectorResult:
        url = self._to_url(input_value, target_type)
        return ConnectorResult(
            detected_source="reddit",
            canonical_url=normalize_canonical_url(url),
        )

    def _to_url(self, input_value: str, target_type: str) -> str:
        if target_type == "url":
            return _normalize_reddit_url(input_value)
        return f"https://www.reddit.com/user/{input_value.lstrip('u/')}"

    async def fetch_and_parse(self, url: str) -> ScraperResult:
        url = _normalize_reddit_url(url)
        try:
            body, status, headers, scraped = await run_playwright_session(
                url,
                _extract_reddit,
                api_url_patterns=None,
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
                    parse_result.profiles.append(
                        {
                            "source": SOURCE,
                            "source_id": url.split("/")[-1] if "/" in url else "",
                            "username": url.split("/")[-1] if "/" in url else "",
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
                "Reddit fetch_and_parse failed",
                extra={"url": url[:80], "error": str(e)},
            )
            return ScraperResult(status="not_collectible", reason=str(e))
