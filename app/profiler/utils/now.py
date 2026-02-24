"""Timestamp utilities."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


def format_timestamp_iso(dt: datetime) -> str:
    """Format datetime for blob path: YYYYMMDDTHHMMSSZ."""
    return dt.strftime("%Y%m%dT%H%M%SZ")
