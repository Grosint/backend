from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime
from typing import Any

from beanie import Document, Indexed, Insert, Replace, before_event
from pydantic import BaseModel, Field

from app.utils.encryption import get_encryption
from app.utils.validators import PyObjectId

logger = logging.getLogger(__name__)


class HistorySourceResult(BaseModel):
    source: str
    success: bool
    latencyMs: int | None = None
    data: dict[str, Any] | None = None
    errorCode: str | None = None
    message: str | None = None


class HistoryMetadata(BaseModel):
    totalSources: int = 0
    successfulSources: int = 0
    failedSources: int = 0
    startedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completedAt: datetime | None = None
    durationMs: int | None = None


class History(Document):
    userId: Indexed(PyObjectId) | None = None
    queryType: str
    # queryInput is NOT encrypted - kept plain for indexing and analysis
    queryInput: dict[str, Any] | str
    status: str = "IN_PROGRESS"  # IN_PROGRESS | COMPLETED | PARTIAL | FAILED
    # results can be list when decrypted, or str when encrypted
    results: list[HistorySourceResult] | str = Field(default_factory=list)
    # flattenedResults can be list when decrypted, or str when encrypted
    flattenedResults: list[dict[str, Any]] | str = Field(
        default_factory=list, description="Flattened results for easy UI rendering"
    )
    metadata: HistoryMetadata = Field(default_factory=HistoryMetadata)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def _is_encrypted_string(self, value: Any) -> bool:
        """
        Check if a value is an encrypted string (base64 encoded).

        Args:
            value: Value to check

        Returns:
            True if value appears to be encrypted
        """
        if not isinstance(value, str):
            return False
        # Encrypted strings are base64 encoded and typically longer
        # Check if it's valid base64 and has reasonable length
        try:
            decoded = base64.b64decode(value, validate=True)
            # Encrypted data should be at least 20 bytes (nonce + some ciphertext)
            return len(decoded) >= 20
        except Exception:
            return False

    @before_event([Insert, Replace])
    def set_timestamps(self):
        now = datetime.now(UTC)
        if self.createdAt is None:
            self.createdAt = now
        self.updatedAt = now

    @before_event([Insert, Replace])
    def encrypt_sensitive_data(self):
        """Encrypt sensitive fields (results and flattenedResults) before saving to database.

        Note: queryInput is NOT encrypted to allow indexing and analysis.
        """
        try:
            encryption = get_encryption()

            # Encrypt results if not empty and not already encrypted
            if self.results and not isinstance(self.results, str):
                self.results = encryption.encrypt(self.results)

            # Encrypt flattenedResults if not empty and not already encrypted
            if self.flattenedResults and not isinstance(self.flattenedResults, str):
                self.flattenedResults = encryption.encrypt(self.flattenedResults)

        except Exception as e:
            logger.error(f"Error encrypting history data: {e}", exc_info=True)
            # Don't raise - allow save to proceed, but log the error
            # In production, you might want to raise here

    def decrypt_sensitive_data(self):
        """Decrypt sensitive fields (results and flattenedResults) after loading from database.

        Note: queryInput is NOT encrypted, so no decryption needed.
        """
        try:
            encryption = get_encryption()

            # Decrypt results if encrypted
            if (
                self.results
                and isinstance(self.results, str)
                and self._is_encrypted_string(self.results)
            ):
                decrypted_results = encryption.decrypt(self.results)
                # Convert list of dicts back to list of HistorySourceResult objects
                if isinstance(decrypted_results, list):
                    self.results = [
                        HistorySourceResult(**item) if isinstance(item, dict) else item
                        for item in decrypted_results
                    ]
                else:
                    self.results = decrypted_results

            # Decrypt flattenedResults if encrypted
            if (
                self.flattenedResults
                and isinstance(self.flattenedResults, str)
                and self._is_encrypted_string(self.flattenedResults)
            ):
                self.flattenedResults = encryption.decrypt(self.flattenedResults)

        except Exception as e:
            logger.error(f"Error decrypting history data: {e}", exc_info=True)
            # Don't raise - return data as-is, but log the error

    class Settings:
        name = "histories"
        indexes = [
            "userId",
            [
                ("createdAt", -1),
            ],
        ]
