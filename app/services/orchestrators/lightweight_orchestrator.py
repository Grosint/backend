"""Lightweight orchestrator for simple searches that call 1-3 APIs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class LightweightOrchestrator:
    """Base for searches that call 1-3 APIs and combine results into standard format."""

    def __init__(
        self,
        name: str,
        services: list[tuple[str, Callable[..., Awaitable[dict[str, Any]]]]],
    ):
        """
        Args:
            name: Orchestrator display name
            services: List of (source_name, async_search_fn). Each fn should accept
                      **kwargs and return {found, data?, error?, confidence?}
        """
        self.name = name
        self.services = services

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Run all services in parallel and combine into lookup_results format.

        Returns:
            dict with lookup_results: {source_name: result}, summary: {...}
        """
        tasks = [fn(**kwargs) for _, fn in self.services]
        service_names = [name for name, _ in self.services]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        lookup_results: dict[str, Any] = {}
        successful_sources = 0

        for i, result in enumerate(results):
            source_name = service_names[i]
            if isinstance(result, Exception):
                logger.error(f"{self.name} service {source_name} failed: {result}")
                lookup_results[source_name] = {
                    "found": False,
                    "error": str(result),
                    "confidence": 0.0,
                }
            else:
                lookup_results[source_name] = result
                if result.get("found", False):
                    successful_sources += 1

        return {
            "lookup_results": lookup_results,
            "summary": {
                "total_sources": len(self.services),
                "successful_sources": successful_sources,
                "found_data": successful_sources > 0,
            },
        }
