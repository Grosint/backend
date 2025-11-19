from __future__ import annotations

import logging
from typing import Any

from app.adapters.social_media_adapter import SocialMediaAdapter

logger = logging.getLogger(__name__)


class SocialMediaOrchestrator:
    """Orchestrator for social media external APIs"""

    def __init__(self):
        self.name = "SocialMediaOrchestrator"
        self.adapter = SocialMediaAdapter()

    async def search_email(self, email: str) -> dict[str, Any]:
        """Search email across social media platforms"""
        try:
            logger.info(f"SocialMediaOrchestrator: Searching email {email}")
            result = await self.adapter.search_email(email)
            return result
        except Exception as e:
            logger.error(f"SocialMediaOrchestrator email search failed: {e}")
            raise

    async def search_domain(self, domain: str) -> dict[str, Any]:
        """Search domain across social media platforms"""
        try:
            logger.info(f"SocialMediaOrchestrator: Searching domain {domain}")
            result = await self.adapter.search_domain(domain)
            return result
        except Exception as e:
            logger.error(f"SocialMediaOrchestrator domain search failed: {e}")
            raise
