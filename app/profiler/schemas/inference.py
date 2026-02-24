"""Inference contract schemas - ML plug-in boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal[
    "image_summary",
    "text_summary",
    "entity_resolution",
    "topic_model",
    "sentiment_summary",
    "nsfw_media_flag",
    "face_cluster",
    "ocr_extract",
]

RefType = Literal["entity_id", "source_document_id", "blob_path", "url"]


class InferenceInputRef(BaseModel):
    """Reference to input for inference."""

    ref_type: RefType
    ref: str
    mime_type: str | None = None


class InferenceContext(BaseModel):
    """Context for inference request."""

    org_id: str
    case_id: str
    target_id: str
    job_id: str = ""
    policy_tier: str = "default"
    locale: str | None = None
    redactions_required: bool = True
    required_citations: bool = True


class InferenceConstraints(BaseModel):
    """Constraints for inference output."""

    max_output_chars: int | None = None
    allowed_labels: list[str] | None = None
    require_explanations: bool = True


class InferenceRequest(BaseModel):
    """Inference request - stored in job payload."""

    task_type: TaskType
    inputs: list[InferenceInputRef]
    context: InferenceContext
    constraints: InferenceConstraints = Field(default_factory=InferenceConstraints)


class InferenceResponse(BaseModel):
    """Inference response from client."""

    enabled: bool
    output: dict = Field(default_factory=dict)
    confidence: float | None = None
    explanations: dict | None = None
    model_version: str = "disabled"
    policy_flags: list[str] = Field(default_factory=list)
