"""Gating detection for NOT_COLLECTIBLE - login walls, auth required, etc."""

from __future__ import annotations

import re

# Phrases that indicate login/age wall when in close proximity in HTML
LOGIN_WALL_PHRASES = [
    r"log\s*in",
    r"login",
    r"sign\s*in",
    r"sign\s*up",
    r"to\s*continue",
    r"continue\s*to",
]

# Combined pattern: "log in" or "login" or "sign in" near "to continue"
LOGIN_WALL_PATTERN = re.compile(
    r"(?:log\s*in|login|sign\s*in)\s*[^\w<>]*\s*(?:to\s*continue|continue)",
    re.IGNORECASE | re.DOTALL,
)


def is_login_wall(html: str | bytes) -> bool:
    """
    Detect if HTML content indicates a login wall / interstitial gate.

    Uses simple heuristics: login/sign-in phrases in proximity to "to continue".
    No evasion or CAPTCHA bypass - purely detect and mark NOT_COLLECTIBLE.
    """
    if not html:
        return False
    text = html.decode("utf-8", errors="ignore") if isinstance(html, bytes) else html
    text_lower = text.lower()
    # Check for common login wall patterns
    if LOGIN_WALL_PATTERN.search(text_lower):
        return True
    # Fallback: "sign in" and "to continue" within ~100 chars
    sign_in_pos = text_lower.find("sign in")
    if sign_in_pos >= 0:
        window = text_lower[sign_in_pos : sign_in_pos + 120]
        if "to continue" in window or "continue" in window:
            return True
    return False
