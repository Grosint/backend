"""Inference client - ML plug-in boundary (disabled by default)."""

from __future__ import annotations

from typing import Protocol

from app.profiler.schemas.inference import InferenceRequest, InferenceResponse


class InferenceClient(Protocol):
    """Protocol for inference client."""

    async def run(self, req: InferenceRequest) -> InferenceResponse:
        """Run inference. Returns response with enabled/output/model_version."""
        ...


class DisabledInferenceClient:
    """Disabled inference - returns enabled=false, no processing."""

    async def run(self, req: InferenceRequest) -> InferenceResponse:
        return InferenceResponse(
            enabled=False,
            output={},
            model_version="disabled",
            policy_flags=["INFERENCE_NOT_ENABLED"],
        )
