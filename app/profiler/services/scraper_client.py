"""Playwright-based scraper client for JS-rendered pages."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.profiler.utils.gating import is_login_wall

logger = logging.getLogger(__name__)

# Skip headers that must not be stored
_SANITIZE_SKIP = {"cookie", "authorization", "set-cookie", "x-csrf-token"}


class PlaywrightScraperClient:
    """Fetch HTML via headless Chromium for JS-rendered social profiles."""

    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        user_agent: str | None = None,
    ) -> None:
        self._timeout_ms = int(
            (timeout_seconds or settings.PROFILER_PUBLIC_FETCH_TIMEOUT_SECONDS) * 1000
        )
        self._user_agent = user_agent or settings.PROFILER_PUBLIC_USER_AGENT

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Remove cookies and auth-related headers from stored copy."""
        return {k: v for k, v in headers.items() if k.lower() not in _SANITIZE_SKIP}

    async def fetch_html(self, url: str) -> tuple[bytes, int, dict[str, str]]:
        """
        Fetch page via Playwright. Returns (body, status_code, sanitized_headers).
        Raises on network/Playwright errors.
        """
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            try:
                context = await browser.new_context(
                    user_agent=self._user_agent,
                    viewport={"width": 1280, "height": 720},
                )
                page = await context.new_page()

                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self._timeout_ms,
                )

                if response is None:
                    raise RuntimeError("No response from navigation")

                status = response.status

                if status in (401, 403):
                    return (b"", status, {})

                await page.wait_for_load_state("networkidle", timeout=self._timeout_ms)

                html = await page.content()
                body = html.encode("utf-8")

                if is_login_wall(body):
                    return (body, status, {})

                raw_headers = response.headers
                if hasattr(raw_headers, "items"):
                    headers = self._sanitize_headers(dict(raw_headers))
                else:
                    headers = {}

                return (body, status, headers)
            finally:
                await browser.close()
