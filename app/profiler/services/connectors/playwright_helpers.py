"""Shared Playwright helpers for social platform scraping."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any

from app.core.config import settings
from app.profiler.utils.gating import is_login_wall

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def run_playwright_session(
    url: str,
    extract_fn: Callable,
    *,
    api_url_patterns: list[str] | None = None,
    timeout_ms: int | None = None,
    user_agent: str | None = None,
    wait_after_load_ms: int = 5000,
    max_scrolls: int = 5,
    wait_until: str = "domcontentloaded",
) -> tuple[bytes, int, dict[str, str], dict[str, Any]]:
    """
    Run a Playwright session: navigate, scroll, call extract_fn(page, api_responses).
    Returns (html_bytes, status_code, headers, extracted_data).

    extract_fn: async (page, api_responses) -> dict
    api_url_patterns: if provided, intercept responses matching any pattern and pass JSON bodies.
    """
    from playwright.async_api import async_playwright

    timeout = timeout_ms or int(settings.PROFILER_PUBLIC_FETCH_TIMEOUT_SECONDS * 1000)
    ua = (
        user_agent
        or getattr(settings, "PROFILER_PUBLIC_USER_AGENT", None)
        or _DEFAULT_USER_AGENT
    )

    api_responses: list[dict[str, Any]] = []

    async def handle_response(response):
        with contextlib.suppress(Exception):
            url_str = response.url
            if api_url_patterns and any(p in url_str for p in api_url_patterns):
                with contextlib.suppress(Exception):
                    data = await response.json()
                    api_responses.append({"url": url_str, "data": data})

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=ua,
            )
            page = await context.new_page()
            if api_url_patterns:
                page.on("response", handle_response)

            response = await page.goto(
                url,
                wait_until=wait_until,
                timeout=timeout,
            )

            if response is None:
                raise RuntimeError("No response from navigation")

            status = response.status
            if status in (401, 403):
                return (b"", status, {}, {})

            await asyncio.sleep(wait_after_load_ms / 1000.0)

            # Scroll to trigger lazy loading / API requests.
            # Use explicit timeout on evaluate: X/social pages can have a busy main thread;
            # default 30s can be hit, causing job failure. 15s per evaluate is sufficient.
            eval_timeout_ms = 15000
            for _ in range(max_scrolls):
                try:
                    await page.evaluate(
                        "() => { window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); }",
                        timeout=eval_timeout_ms,
                    )
                except Exception:
                    break
                await asyncio.sleep(3.0)
                try:
                    is_bottom = await page.evaluate(
                        """
                        () => {
                            const sh = document.documentElement.scrollHeight || document.body.scrollHeight;
                            const st = window.pageYOffset || document.documentElement.scrollTop;
                            const ch = window.innerHeight || document.documentElement.clientHeight;
                            return (st + ch) >= sh - 100;
                        }
                        """,
                        timeout=eval_timeout_ms,
                    )
                except Exception:
                    break
                if is_bottom:
                    break
                await asyncio.sleep(1.0)

            await asyncio.sleep(2.0)

            extracted = await extract_fn(page, api_responses)
            html = await page.content()
            body = html.encode("utf-8")

            if is_login_wall(body):
                return (body, status, {}, extracted)

            raw_headers = response.headers
            headers = dict(raw_headers) if hasattr(raw_headers, "items") else {}
            skip = {"cookie", "authorization", "set-cookie", "x-csrf-token"}
            headers = {k: v for k, v in headers.items() if k.lower() not in skip}

            return (body, status, headers, extracted)
        finally:
            await browser.close()
