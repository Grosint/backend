"""X (Twitter) public connector - Playwright scrape with API/DOM extraction."""

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

SOURCE = "x"

_X_API_PATTERNS = [
    "/2/timeline/profile/",
    "/2/timeline/home.json",
    "/1.1/statuses/user_timeline.json",
    "/graphql/",
    "/api/graphql",
    "/TweetDetail",
    "/UserTweets",
    "/UserByScreenName",
    "/TweetResultByRestId",
    "/HomeTimeline",
    "/SearchTimeline",
]


def _normalize_x_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if "twitter.com/" in url or "x.com/" in url:
        m = re.search(r"(?:twitter\.com|x\.com)/([^/?]+)", url)
        if m:
            return f"https://x.com/{m.group(1).lstrip('@')}"
    if not url.startswith("http"):
        return f"https://x.com/{url.lstrip('@')}"
    return url


def _parse_tweet_legacy(legacy: dict) -> dict[str, Any]:
    return {
        "id": legacy.get("id_str"),
        "text": legacy.get("full_text") or legacy.get("text", ""),
        "retweet_count": legacy.get("retweet_count", 0),
        "favorite_count": legacy.get("favorite_count", 0),
        "reply_count": legacy.get("reply_count", 0),
    }


def _parse_tweet_from_graphql(tweet_result: dict) -> dict[str, Any] | None:
    try:
        td = tweet_result.get("tweet", tweet_result) or tweet_result
        legacy = (td.get("legacy") if "legacy" in td else td) or {}
        if not legacy.get("id_str"):
            return None
        t = _parse_tweet_legacy(legacy)
        if "core" in td and "user_results" in td["core"]:
            ur = td["core"]["user_results"].get("result", {})
            if "legacy" in ur:
                ul = ur["legacy"]
                t["author"] = {
                    "username": ul.get("screen_name"),
                    "name": ul.get("name"),
                }
        return t
    except Exception:
        return None


def _find_tweets_in_api(obj: Any, depth: int = 0) -> list[dict]:
    if depth > 15:
        return []
    found = []
    if isinstance(obj, dict):
        if "user" in obj:
            u = obj["user"]
            if isinstance(u, dict) and "result" in u:
                r = u["result"]
                tl = (r.get("timeline") or {}).get("timeline") or {}
                for instr in tl.get("instructions", []):
                    for entry in instr.get("entries", []):
                        ic = entry.get("content", {}).get("itemContent", {})
                        tr = (ic.get("tweet_results") or {}).get("result", {})
                        t = _parse_tweet_from_graphql(tr)
                        if t:
                            found.append(t)
        if "data" in obj and isinstance(obj["data"], list):
            for item in obj["data"]:
                tid = item.get("id")
                if tid:
                    t = {
                        "id": tid,
                        "text": item.get("text", ""),
                        "retweet_count": (item.get("public_metrics") or {}).get(
                            "retweet_count", 0
                        ),
                        "favorite_count": (item.get("public_metrics") or {}).get(
                            "like_count", 0
                        ),
                        "reply_count": (item.get("public_metrics") or {}).get(
                            "reply_count", 0
                        ),
                    }
                    found.append(t)
        if "statuses" in obj:
            for s in obj["statuses"]:
                t = _parse_tweet_legacy(s) if s.get("id_str") else None
                if t:
                    found.append(t)
        for v in obj.values():
            found.extend(_find_tweets_in_api(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_find_tweets_in_api(item, depth + 1))
    return found


def _dedupe_tweets(tweets: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for t in tweets:
        key = t.get("id") or t.get("tweet_id")
        if key and key not in seen:
            seen.add(key)
            unique.append(t)
        elif not key and t.get("text"):
            h = hash(t.get("text", "")[:100])
            if h not in seen:
                seen.add(h)
                unique.append(t)
    return unique


async def _extract_x(page, api_responses: list[dict]) -> dict[str, Any]:
    tweets = []
    for r in api_responses:
        with contextlib.suppress(Exception):
            tweets.extend(_find_tweets_in_api(r))
    try:
        tweets_js = await page.evaluate(
            """
            () => {
                const tweets = [];
                try {
                    if (window.__INITIAL_STATE__?.entities?.tweets) {
                        Object.values(window.__INITIAL_STATE__.entities.tweets).forEach(t => {
                            tweets.push({
                                id: t.id_str || t.id,
                                text: t.full_text || t.text,
                                retweet_count: t.retweet_count || 0,
                                favorite_count: t.favorite_count || 0
                            });
                        });
                    }
                } catch (e) {}
                return tweets;
            }
            """
        )
        for t in tweets_js:
            if (
                t
                and (t.get("id") or t.get("text"))
                and not any(x.get("id") == t.get("id") for x in tweets)
            ):
                tweets.append(t)
    except Exception as e:
        logger.debug("X JS extract: %s", e)
    try:
        dom_tweets = await page.evaluate(
            """
            () => {
                const tweets = [];
                document.querySelectorAll('article[data-testid="tweet"]').forEach((art, i) => {
                    if (i < 20) {
                        const textEl = art.querySelector('[data-testid="tweetText"]');
                        const text = textEl ? textEl.innerText : '';
                        const id = art.getAttribute('data-tweet-id') ||
                            art.querySelector('a[href*="/status/"]')?.href?.match(/\\/status\\/(\\d+)/)?.[1] || '';
                        if (text || id) tweets.push({ id, text, source: 'dom' });
                    }
                });
                return tweets;
            }
            """
        )
        for t in dom_tweets:
            if (
                t
                and (t.get("id") or t.get("text"))
                and not any(x.get("id") == t.get("id") and x.get("id") for x in tweets)
            ):
                tweets.append(t)
    except Exception as e:
        logger.debug("X DOM extract: %s", e)
    unique_tweets = _dedupe_tweets(tweets)
    profile_info: dict[str, Any] = {}
    try:
        page_data = await page.evaluate(
            """
            () => {
                const d = {};
                try {
                    if (window.__NEXT_DATA__?.props?.pageProps?.user) {
                        d.user = window.__NEXT_DATA__.props.pageProps.user;
                    }
                    if (window.__INITIAL_STATE__?.entities?.users) {
                        d.users = window.__INITIAL_STATE__.entities.users;
                    }
                } catch (e) {}
                return d;
            }
            """
        )
        if page_data.get("user"):
            u = page_data["user"]
            profile_info = {
                "username": u.get("screen_name") or u.get("username"),
                "name": u.get("name"),
                "description": u.get("description") or u.get("bio"),
                "followers_count": u.get("followers_count"),
                "following_count": u.get("friends_count") or u.get("following_count"),
                "verified": u.get("verified", False),
            }
        elif page_data.get("users"):
            users = page_data["users"]
            if users:
                u = next(iter(users.values())) if isinstance(users, dict) else users[0]
                profile_info = {
                    "username": u.get("screen_name"),
                    "name": u.get("name"),
                    "description": u.get("description"),
                    "followers_count": u.get("followers_count"),
                    "following_count": u.get("friends_count"),
                    "verified": u.get("verified", False),
                }
    except Exception as e:
        logger.debug("X profile extract: %s", e)
    return {"profile_info": profile_info, "tweets": unique_tweets}


def _scraped_to_parse_result(
    url: str, html: str, scraped: dict[str, Any]
) -> ParseResult:
    result = ParseResult()
    profile_info = scraped.get("profile_info", {})
    tweets = scraped.get("tweets", [])
    username = profile_info.get("username", "")
    if not username:
        from urllib.parse import urlparse

        parts = urlparse(url).path.strip("/").split("/")
        username = parts[0].lstrip("@") if parts else ""
    if username or profile_info.get("name"):
        result.profiles.append(
            {
                "source": SOURCE,
                "source_id": username,
                "username": username,
                "display_name": profile_info.get("name", username),
                "bio": profile_info.get("description", ""),
                "followers_count": profile_info.get("followers_count"),
                "following_count": profile_info.get("following_count"),
            }
        )
    for tw in tweets:
        tid = tw.get("id", "") or ""
        text = tw.get("text", "")
        if not tid and text:
            tid = hashlib.md5(text[:200].encode(), usedforsecurity=False).hexdigest()[
                :16
            ]
        result.posts.append(
            {
                "source": SOURCE,
                "source_post_id": tid,
                "text_content": text,
                "engagement_counts": {
                    "retweets": tw.get("retweet_count", 0),
                    "likes": tw.get("favorite_count", 0) or tw.get("like_count", 0),
                    "replies": tw.get("reply_count", 0),
                },
            }
        )
        for tag in extract_hashtags(text):
            result.tags.append({"source": SOURCE, "tag": tag, "post_id": tid})
        for mention in extract_mentions(text):
            result.interactions.append(
                {
                    "source": SOURCE,
                    "counterparty_username": mention,
                    "interaction_type": "mention",
                }
            )
    return result


class XPublicConnector:
    """X/Twitter public - Playwright scrape with API/JS/DOM extraction."""

    def resolve(self, input_value: str, target_type: str) -> ConnectorResult:
        url = self._to_url(input_value, target_type)
        return ConnectorResult(
            detected_source="x",
            canonical_url=normalize_canonical_url(url),
        )

    def _to_url(self, input_value: str, target_type: str) -> str:
        if target_type == "url":
            return _normalize_x_url(input_value)
        return f"https://x.com/{input_value.lstrip('@')}"

    async def fetch_and_parse(self, url: str) -> ScraperResult:
        url = _normalize_x_url(url)
        try:
            body, status, headers, scraped = await run_playwright_session(
                url,
                _extract_x,
                api_url_patterns=_X_API_PATTERNS,
                wait_until="domcontentloaded",
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
                "X fetch_and_parse failed", extra={"url": url[:80], "error": str(e)}
            )
            return ScraperResult(status="not_collectible", reason=str(e))
