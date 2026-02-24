"""Hashing utilities for evidence provenance."""

from __future__ import annotations

import hashlib


def sha256_bytes(data: bytes) -> str:
    """Compute SHA256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()
