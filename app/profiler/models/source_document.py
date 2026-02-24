"""ProfilerSourceDocument Beanie document."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId

FetchMethod = Literal["http", "scrape"]


class ProfilerSourceDocument(Document):
    """Profiler source document - raw captured evidence with provenance."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    job_id: PyObjectId
    url: str
    captured_at: datetime
    http_status: int
    headers: dict = Field(default_factory=dict)
    content_type: str | None = None
    fetch_method: FetchMethod = "http"
    sha256: str
    blob_path: str
    parser_version: str = "v1"

    class Settings:
        name = "profiler_source_documents"
        indexes = [
            IndexModel([("org_id", 1)], name="org_id_idx"),
            IndexModel([("case_id", 1)], name="case_id_idx"),
            IndexModel([("target_id", 1)], name="target_id_idx"),
            IndexModel([("job_id", 1)], name="job_id_idx"),
            IndexModel([("captured_at", -1)], name="captured_at_idx"),
            IndexModel([("sha256", 1)], name="sha256_idx"),
        ]
