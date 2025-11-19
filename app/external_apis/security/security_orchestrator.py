from __future__ import annotations

import logging
from typing import Any

from app.adapters.security_adapter import SecurityAdapter
from app.core.logging import hash_identifier

logger = logging.getLogger(__name__)


class SecurityOrchestrator:
    """Orchestrator for security external APIs"""

    def __init__(self):
        self.name = "SecurityOrchestrator"
        self.adapter = SecurityAdapter()

    async def search_email(self, email: str) -> dict[str, Any]:
        """Search email across security platforms"""
        email_hash = hash_identifier(email)
        try:
            logger.info(
                "SecurityOrchestrator: Searching email",
                extra={"email_hash": email_hash, "identifier_type": "email"},
            )
            result = await self.adapter.search_email(email)
            return result
        except Exception as e:
            logger.error(
                "SecurityOrchestrator email search failed",
                extra={
                    "email_hash": email_hash,
                    "identifier_type": "email",
                    "exception": type(e).__name__,
                },
            )
            raise

    async def search_domain(self, domain: str) -> dict[str, Any]:
        """Search domain across security platforms"""
        domain_hash = hash_identifier(domain)
        try:
            logger.info(
                "SecurityOrchestrator: Searching domain",
                extra={"domain_hash": domain_hash, "identifier_type": "domain"},
            )
            result = await self.adapter.search_domain(domain)
            return result
        except Exception as e:
            logger.error(
                "SecurityOrchestrator domain search failed",
                extra={
                    "domain_hash": domain_hash,
                    "identifier_type": "domain",
                    "exception": type(e).__name__,
                },
            )
            raise
