"""LinkedIn public connector - Playwright scrape with DOM extraction."""

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

SOURCE = "linkedin"


def _normalize_linkedin_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if "linkedin.com/in/" in url:
        m = re.search(r"linkedin\.com/in/([^/?]+)", url)
        if m:
            return f"https://www.linkedin.com/in/{m.group(1)}"
    if not url.startswith("http"):
        return f"https://www.linkedin.com/in/{url}"
    return url


async def _extract_linkedin(page, api_responses: list) -> dict[str, Any]:
    profile_info: dict[str, Any] = {}
    try:
        profile_info = (
            await page.evaluate(
                """
            () => {
                const data = {};
                const nameEl = document.querySelector('h1.text-heading-xlarge') ||
                    document.querySelector('h1[class*="text-heading"]') || document.querySelector('h1');
                if (nameEl) data.name = nameEl.innerText.trim();
                const headlineEl = document.querySelector('.text-body-medium.break-words') ||
                    document.querySelector('[class*="headline"]');
                if (headlineEl) data.headline = headlineEl.innerText.trim();
                const locationEl = document.querySelector('.text-body-small.inline.t-black--light.break-words');
                if (locationEl) data.location = locationEl.innerText.trim();
                const aboutEl = document.querySelector('#about ~ .inline-show-more-text') ||
                    document.querySelector('[id*="about"]');
                if (aboutEl) data.about = aboutEl.innerText.trim();
                return data;
            }
            """
            )
            or {}
        )
    except Exception as e:
        logger.debug("LinkedIn profile extract: %s", e)
    posts: list[dict[str, Any]] = []
    try:
        posts = (
            await page.evaluate(
                """
            () => {
                const posts = [];
                document.querySelectorAll('.feed-shared-update-v2').forEach((el, i) => {
                    if (i < 20) {
                        const textEl = el.querySelector('.feed-shared-text span[dir="ltr"]') ||
                            el.querySelector('.feed-shared-text');
                        const text = textEl ? textEl.innerText.trim() : '';
                        const timeEl = el.querySelector('time');
                        if (text) posts.push({
                            id: 'post_' + i,
                            text: text,
                            created_at: timeEl ? timeEl.getAttribute('datetime') : null
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
        logger.debug("LinkedIn posts extract: %s", e)
    return {"profile_info": profile_info, "posts": posts}


def _scraped_to_parse_result(
    url: str, html: str, scraped: dict[str, Any]
) -> ParseResult:
    result = ParseResult()
    profile_info = scraped.get("profile_info", {})
    posts = scraped.get("posts", [])
    from urllib.parse import urlparse

    parts = urlparse(url).path.strip("/").split("/")
    username = parts[-1] if parts else ""
    name = profile_info.get("name", "")
    headline = profile_info.get("headline", "")
    about = profile_info.get("about", "")
    if username or name:
        result.profiles.append(
            {
                "source": SOURCE,
                "source_id": username,
                "username": username,
                "display_name": name or username,
                "bio": (headline or "") + (" " + about if about else ""),
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
    return result


class LinkedInPublicConnector:
    """LinkedIn public - Playwright scrape with DOM extraction."""

    def resolve(self, input_value: str, target_type: str) -> ConnectorResult:
        url = self._to_url(input_value, target_type)
        return ConnectorResult(
            detected_source="linkedin",
            canonical_url=normalize_canonical_url(url),
        )

    def _to_url(self, input_value: str, target_type: str) -> str:
        if target_type == "url":
            return _normalize_linkedin_url(input_value)
        return f"https://www.linkedin.com/in/{input_value.lstrip('@')}"

    async def fetch_and_parse(self, url: str) -> ScraperResult:
        url = _normalize_linkedin_url(url)
        try:
            body, status, headers, scraped = await run_playwright_session(
                url,
                _extract_linkedin,
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
                "LinkedIn fetch_and_parse failed",
                extra={"url": url[:80], "error": str(e)},
            )
            return ScraperResult(status="not_collectible", reason=str(e))
