"""Extracted profile schema - canonical JSON structure for scraped data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """Provenance metadata - mandatory for all extractions."""

    raw_url: str
    capture_timestamp: str  # ISO 8601
    http_status: int
    headers: dict[str, str] = Field(default_factory=dict)  # sanitized
    sha256: str
    blob_path: str = ""  # filled after store
    parser_version: str = "v1"


class Identity(BaseModel):
    """Identity and profile fields."""

    handle: str = ""
    display_name: str = ""
    bio: str = ""
    profile_url: str = ""
    profile_image_url: str | None = None
    followers_count: int | None = None
    following_count: int | None = None
    verified: bool | None = None


class PostItem(BaseModel):
    """Single post/tweet/reel."""

    id: str = ""
    url: str = ""
    created_at: str | None = None
    text: str = ""
    media_refs: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    link_urls: list[str] = Field(default_factory=list)
    is_reply: bool | None = None
    in_reply_to: str | None = None


class CommentItem(BaseModel):
    """Single comment/reply."""

    id: str = ""
    url: str = ""
    created_at: str | None = None
    text: str = ""
    author_handle: str = ""
    parent_post_id: str = ""


class Content(BaseModel):
    """Content section - posts and comments."""

    posts: list[PostItem] = Field(default_factory=list)
    comments: list[CommentItem] = Field(default_factory=list)


class InteractionItem(BaseModel):
    """Target -> other account interaction."""

    timestamp: str | None = None
    counterparty_handle: str = ""
    type: str = ""  # mention, reply, tag, etc.
    evidence_pointer: str = ""


class LocationItem(BaseModel):
    """Location/check-in."""

    place_name: str = ""
    lat: float | None = None
    lng: float | None = None
    timestamp: str | None = None
    country_code: str | None = None


class ReviewItem(BaseModel):
    """Google review - empty for FB/IG/X."""

    place_name: str = ""
    category: str = ""
    rating: float | None = None
    review_text: str = ""
    timestamp: str | None = None
    price_range: str | None = None


class ExtractedProfile(BaseModel):
    """Top-level extracted profile - single source of truth stored in Blob."""

    provenance: Provenance
    identity: Identity = Field(default_factory=Identity)
    content: Content = Field(default_factory=Content)
    interactions: list[InteractionItem] = Field(default_factory=list)
    locations: list[LocationItem] = Field(default_factory=list)
    reviews: list[ReviewItem] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return self.model_dump(exclude_none=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedProfile:
        """Deserialize from dict (e.g. from Blob JSON)."""
        return cls.model_validate(data)
