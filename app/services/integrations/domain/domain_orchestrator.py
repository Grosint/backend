from __future__ import annotations

import logging
from typing import Any

from app.adapters.domain_adapter import DomainAdapter

logger = logging.getLogger(__name__)


class DomainOrchestrator:
    """Orchestrator for domain analysis external APIs"""

    def __init__(self):
        self.name = "DomainOrchestrator"
        self.adapter = DomainAdapter()

    async def search_domain(self, domain: str) -> dict[str, Any]:
        """Search domain across domain analysis platforms"""
        try:
            logger.info(f"DomainOrchestrator: Searching domain {domain}")
            result = await self.adapter.search_domain(domain)
            return result
        except Exception as e:
            logger.error(f"DomainOrchestrator domain search failed: {e}")
            raise
