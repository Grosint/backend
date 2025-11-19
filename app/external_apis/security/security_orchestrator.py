from __future__ import annotations

import logging
from typing import Any

from app.adapters.security_adapter import SecurityAdapter

logger = logging.getLogger(__name__)


class SecurityOrchestrator:
    """Orchestrator for security external APIs"""

    def __init__(self):
        self.name = "SecurityOrchestrator"
        self.adapter = SecurityAdapter()

    async def search_email(self, email: str) -> dict[str, Any]:
        """Search email across security platforms"""
        try:
            logger.info(f"SecurityOrchestrator: Searching email {email}")
            result = await self.adapter.search_email(email)
            return result
        except Exception as e:
            logger.error(f"SecurityOrchestrator email search failed: {e}")
            raise

    async def search_domain(self, domain: str) -> dict[str, Any]:
        """Search domain across security platforms"""
        try:
            logger.info(f"SecurityOrchestrator: Searching domain {domain}")
            result = await self.adapter.search_domain(domain)
            return result
        except Exception as e:
            logger.error(f"SecurityOrchestrator domain search failed: {e}")
            raise
