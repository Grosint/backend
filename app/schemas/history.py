from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.response import BaseResponse, PaginatedResponse


class HistorySourceResultSchema(BaseModel):
    source: str
    success: bool
    latencyMs: int | None = None
    data: dict[str, Any] | None = None
    errorCode: str | None = None
    message: str | None = None


class HistoryMetadataSchema(BaseModel):
    totalSources: int
    successfulSources: int
    failedSources: int
    startedAt: datetime
    completedAt: datetime | None = None
    durationMs: int | None = None


class HistorySchema(BaseModel):
    id: str
    userId: str | None = None
    queryType: str
    queryInput: dict[str, Any] | str
    status: str
    results: list[HistorySourceResultSchema]
    metadata: HistoryMetadataSchema
    createdAt: datetime
    updatedAt: datetime


class HistoryResponse(BaseResponse[HistorySchema]):
    pass


class HistoryListResponse(PaginatedResponse[HistorySchema]):
    pass
