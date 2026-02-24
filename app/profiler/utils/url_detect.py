"""URL and source detection utilities."""

from __future__ import annotations

import contextlib
from typing import Literal
from urllib.parse import urlparse

DetectedSource = Literal[
    "x", "instagram", "facebook", "google", "blog", "linkedin", "reddit", "unknown"
]


def detect_source_by_hostname(url: str) -> DetectedSource:
    """Detect platform from URL hostname."""
    with contextlib.suppress(Exception):
        parsed = urlparse(url)
        host = (parsed.netloc or parsed.path).lower()
        if "x.com" in host or "twitter.com" in host:
            return "x"
        if "instagram.com" in host:
            return "instagram"
        if "facebook.com" in host or "fb.com" in host or "fb.watch" in host:
            return "facebook"
        if "linkedin.com" in host:
            return "linkedin"
        if "reddit.com" in host or "redd.it" in host:
            return "reddit"
        if any(
            p in host
            for p in ("medium.com", "substack.com", "wordpress.com", "blogspot.com")
        ):
            return "blog"
        if "google.com" in host or "maps.google" in host:
            return "google"
    return "unknown"


def normalize_canonical_url(url: str) -> str:
    """Normalize URL to canonical form (basic v1)."""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        netloc = (parsed.netloc or "").lower()
        path = parsed.path or "/"
        if not path.startswith("/"):
            path = "/" + path
        # Strip trailing slash for consistency (except root)
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        query = parsed.query
        frag = parsed.fragment
        base = f"{scheme}://{netloc}{path}"
        if query:
            base += "?" + query
        if frag:
            base += "#" + frag
        return base
    except Exception:
        return url
