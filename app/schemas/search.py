from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.search import SearchStatus, SearchType


class SearchRequest(BaseModel):
    """Request schema for creating a search"""

    search_type: SearchType
    query: str = Field(..., min_length=1, max_length=500, description="Search query")


class SearchResponse(BaseModel):
    """Response schema for search operations"""

    id: str
    search_type: SearchType
    query: str
    status: SearchStatus
    results_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class SearchListResponse(BaseModel):
    """Response schema for search list"""

    searches: list[SearchResponse]
    total: int
    page: int
    size: int


class SearchStatsResponse(BaseModel):
    """Response schema for search statistics"""

    total_searches: int
    searches_by_status: dict[str, int]
    searches_by_type: dict[str, int]


class ResultResponse(BaseModel):
    """Response schema for individual results"""

    id: str
    source: str
    data: dict[str, Any]
    confidence_score: float | None = None
    created_at: datetime


class SearchSummaryResponse(BaseModel):
    """Response schema for search summary with results"""

    search: SearchResponse
    results: dict[str, Any]


class SearchCreateResponse(BaseModel):
    """Response schema for search creation"""

    message: str
    search_id: str
    status: str
