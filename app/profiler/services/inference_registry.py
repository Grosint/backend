"""Inference client registry - returns client based on config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings
from app.profiler.services.inference_client import DisabledInferenceClient

if TYPE_CHECKING:
    from app.profiler.services.inference_client import InferenceClient


def get_inference_client() -> InferenceClient:
    """Return inference client based on INFERENCE_MODE."""
    if settings.INFERENCE_MODE == "disabled":
        return DisabledInferenceClient()
    # Future: "http" -> HttpInferenceClient, "local" -> LocalInferenceClient
    return DisabledInferenceClient()
