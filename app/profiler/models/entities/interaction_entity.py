"""InteractionEntity - canonical interaction from any source."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from app.utils.validators import PyObjectId

InteractionType = Literal["comment", "reply", "mention", "tag"]


class InteractionEntity(Document):
    """Normalized interaction entity across all sources."""

    org_id: PyObjectId
    case_id: PyObjectId
    target_id: PyObjectId
    source: str
    actor_profile_id: str
    counterparty_profile_id: str
    interaction_type: InteractionType
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_id: str

    class Settings:
        name = "profiler_entities_interactions"
        indexes = [
            IndexModel([("target_id", 1)], name="target_id_idx"),
            IndexModel([("counterparty_profile_id", 1)], name="counterparty_idx"),
            IndexModel([("created_at", -1)], name="created_at_idx"),
        ]
