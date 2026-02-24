"""Blog/generic web page connector - Playwright scrape with OG meta + BeautifulSoup."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from bs4 import BeautifulSoup

from app.profiler.services.connectors.base import ConnectorResult, ScraperResult
from app.profiler.services.connectors.parsers import (
    ParseResult,
    extract_hashtags,
    extract_mentions,
    extract_og_meta,
    parse_result_to_extracted_profile,
)
from app.profiler.services.connectors.playwright_helpers import run_playwright_session
from app.profiler.utils.gating import is_login_wall
from app.profiler.utils.now import utc_now
from app.profiler.utils.url_detect import normalize_canonical_url

logger = logging.getLogger(__name__)

SOURCE = "blog"


def _normalize_blog_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        return f"https://{url}"
    return url


async def _extract_blog(page, api_responses: list) -> dict[str, Any]:
    return {}


def _html_to_parse_result(url: str, html: str) -> ParseResult:
    result = ParseResult()
    soup = BeautifulSoup(html, "html.parser")
    og = extract_og_meta(html)
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    text = " ".join(soup.stripped_strings) if soup else ""
    title = og.get("title", "")
    description = og.get("description", "") or text[:2000]
    handle = url.replace("https://", "").replace("http://", "").split("/")[0]
    if title or handle:
        result.profiles.append(
            {
                "source": SOURCE,
                "source_id": handle,
                "username": handle,
                "display_name": title or handle,
                "bio": description[:500] if description else "",
            }
        )
    if text or description:
        post_id = hashlib.md5(
            (text or description)[:200].encode(), usedforsecurity=False
        ).hexdigest()[:16]
        result.posts.append(
            {
                "source": SOURCE,
                "source_post_id": post_id,
                "text_content": description or text[:5000],
                "engagement_counts": {},
            }
        )
        for tag in extract_hashtags(description or text):
            result.tags.append({"source": SOURCE, "tag": tag, "post_id": post_id})
        for mention in extract_mentions(description or text):
            result.interactions.append(
                {
                    "source": SOURCE,
                    "counterparty_username": mention,
                    "interaction_type": "mention",
                }
            )
    if og.get("image"):
        mid = hashlib.md5(og["image"].encode(), usedforsecurity=False).hexdigest()[:16]
        result.media.append(
            {
                "source": SOURCE,
                "source_media_id": mid,
                "media_type": "image",
                "url": og["image"],
            }
        )
    return result


class BlogPublicConnector:
    """Blog/generic web page - Playwright scrape with OG meta + text extraction."""

    def resolve(self, input_value: str, target_type: str) -> ConnectorResult:
        url = self._to_url(input_value, target_type)
        return ConnectorResult(
            detected_source="blog",
            canonical_url=normalize_canonical_url(url),
        )

    def _to_url(self, input_value: str, target_type: str) -> str:
        if target_type == "url":
            return _normalize_blog_url(input_value)
        return _normalize_blog_url(input_value)

    async def fetch_and_parse(self, url: str) -> ScraperResult:
        url = _normalize_blog_url(url)
        try:
            body, status, headers, _ = await run_playwright_session(
                url,
                _extract_blog,
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
            parse_result = _html_to_parse_result(url, html)
            if not parse_result.profiles and not parse_result.posts:
                og = extract_og_meta(html)
                if og.get("title") or og.get("description"):
                    parse_result.profiles.append(
                        {
                            "source": SOURCE,
                            "source_id": url.split("/")[2] if "/" in url else "",
                            "username": url.split("/")[2] if "/" in url else "",
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
                "Blog fetch_and_parse failed", extra={"url": url[:80], "error": str(e)}
            )
            return ScraperResult(status="not_collectible", reason=str(e))
