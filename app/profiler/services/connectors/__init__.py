"""Profiler connectors for source detection."""

from app.profiler.services.connectors.base import ConnectorResult, ScraperResult
from app.profiler.services.connectors.public import (
    BlogPublicConnector,
    FacebookPublicConnector,
    InstagramPublicConnector,
    LinkedInPublicConnector,
    RedditPublicConnector,
    XPublicConnector,
)
from app.profiler.utils.url_detect import (
    detect_source_by_hostname,
    normalize_canonical_url,
)

__all__ = [
    "BlogPublicConnector",
    "ConnectorResult",
    "FacebookPublicConnector",
    "InstagramPublicConnector",
    "LinkedInPublicConnector",
    "RedditPublicConnector",
    "ScraperResult",
    "XPublicConnector",
    "detect_source_by_hostname",
    "normalize_canonical_url",
]
