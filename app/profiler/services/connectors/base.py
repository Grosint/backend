"""Base connector interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DetectedSource = Literal[
    "x", "instagram", "facebook", "google", "blog", "linkedin", "reddit", "unknown"
]

ScraperStatus = Literal["collected", "not_collectible"]


@dataclass
class ConnectorResult:
    """Result from source connector - v1 minimal."""

    detected_source: DetectedSource
    canonical_url: str


@dataclass
class ScraperResult:
    """Result from connector fetch_and_parse - scraped profile data or error."""

    status: ScraperStatus
    extracted: dict | None = None
    reason: str | None = None
