from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime
from typing import Any

from beanie import Document, Indexed, Insert, Replace, Update, before_event
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

    @before_event([Insert, Replace, Update])
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
        encryption = get_encryption()
        if encryption is None:
            history_id = str(self.id) if hasattr(self, "id") and self.id else "new"
            error_msg = f"CRITICAL: Encryption not available (ENCRYPTION_KEY missing) for history_id={history_id}"
            logger.error(error_msg, extra={"history_id": history_id})

            # Fail the save in ALL environments to prevent unencrypted data storage
            # This ensures data integrity and security regardless of environment
            raise ValueError(
                "Encryption not available (ENCRYPTION_KEY missing). "
                "Save operation aborted to prevent storing unencrypted sensitive data. "
                "ENCRYPTION_KEY must be set. Generate one with: openssl rand -base64 32"
            )

        try:
            # Encrypt results if not already encrypted
            # Note: Empty lists are still encrypted to maintain consistency
            if not isinstance(self.results, str):
                logger.info(
                    f"Encrypting results: type={type(self.results).__name__}, "
                    f"is_list={isinstance(self.results, list)}, "
                    f"len={len(self.results) if isinstance(self.results, list) else 'N/A'}",
                    extra={
                        "history_id": (
                            str(self.id) if hasattr(self, "id") and self.id else "new"
                        )
                    },
                )
                # Convert Pydantic models to dicts before encryption
                if isinstance(self.results, list):
                    results_data = [
                        item.model_dump() if isinstance(item, BaseModel) else item
                        for item in self.results
                    ]
                elif isinstance(self.results, BaseModel):
                    results_data = self.results.model_dump()
                else:
                    results_data = self.results
                # Encrypt even if empty list to maintain consistency
                encrypted_results = encryption.encrypt(results_data)
                self.results = encrypted_results
                logger.info(
                    f"Results encrypted successfully: encrypted_length={len(encrypted_results)}",
                    extra={
                        "history_id": (
                            str(self.id) if hasattr(self, "id") and self.id else "new"
                        )
                    },
                )

            # Encrypt flattenedResults if not already encrypted
            # Note: Empty lists are still encrypted to maintain consistency
            if not isinstance(self.flattenedResults, str):
                logger.info(
                    f"Encrypting flattenedResults: type={type(self.flattenedResults).__name__}, "
                    f"is_list={isinstance(self.flattenedResults, list)}, "
                    f"len={len(self.flattenedResults) if isinstance(self.flattenedResults, list) else 'N/A'}",
                    extra={
                        "history_id": (
                            str(self.id) if hasattr(self, "id") and self.id else "new"
                        )
                    },
                )
                # Convert Pydantic models to dicts before encryption
                if isinstance(self.flattenedResults, list):
                    flattened_data = [
                        item.model_dump() if isinstance(item, BaseModel) else item
                        for item in self.flattenedResults
                    ]
                elif isinstance(self.flattenedResults, BaseModel):
                    flattened_data = self.flattenedResults.model_dump()
                else:
                    flattened_data = self.flattenedResults
                # Encrypt even if empty list to maintain consistency
                encrypted_flattened = encryption.encrypt(flattened_data)
                self.flattenedResults = encrypted_flattened
                logger.info(
                    f"FlattenedResults encrypted successfully: encrypted_length={len(encrypted_flattened)}",
                    extra={
                        "history_id": (
                            str(self.id) if hasattr(self, "id") and self.id else "new"
                        )
                    },
                )

        except Exception as e:
            history_id = str(self.id) if hasattr(self, "id") and self.id else "new"
            error_msg = f"CRITICAL: Failed to encrypt history data for history_id={history_id}: {e}"
            logger.error(error_msg, exc_info=True, extra={"history_id": history_id})

            # Fail the save in ALL environments to prevent unencrypted data storage
            # This ensures data integrity and security regardless of environment
            raise ValueError(
                f"Encryption failed for history data. Save operation aborted to prevent "
                f"storing unencrypted sensitive data. Original error: {str(e)}"
            ) from e

    def decrypt_sensitive_data(self):
        """Decrypt sensitive fields (results and flattenedResults) after loading from database.

        Note: queryInput is NOT encrypted, so no decryption needed.
        """
        encryption = get_encryption()
        if encryption is None:
            # Encryption not available - if data is encrypted, we can't decrypt it
            # Check if data appears to be encrypted and log a warning
            if (
                isinstance(self.results, str)
                and self._is_encrypted_string(self.results)
            ) or (
                isinstance(self.flattenedResults, str)
                and self._is_encrypted_string(self.flattenedResults)
            ):
                logger.warning(
                    "Encrypted history data found but ENCRYPTION_KEY is not set. "
                    "Data will remain encrypted and cannot be decrypted."
                )
            return

        try:
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
            logger.warning(
                "Decryption failed (likely ENCRYPTION_KEY mismatch). Returning empty results. "
                "history_id=%s error=%s",
                str(self.id) if hasattr(self, "id") and self.id else "?",
                str(e)[:100],
            )
            # Graceful degradation: empty results so API returns valid schema
            if isinstance(self.results, str):
                self.results = []
            if isinstance(self.flattenedResults, str):
                self.flattenedResults = []

    class Settings:
        name = "histories"
        indexes = [
            "userId",
            [
                ("createdAt", -1),
            ],
        ]
