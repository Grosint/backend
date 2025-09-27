import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from app.adapters.base import OSINTAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailAdapter(OSINTAdapter):
    """Adapter for email-related OSINT operations"""

    def __init__(self):
        super().__init__()
        self.name = "EmailAdapter"
        self.timeout = settings.EXTERNAL_API_TIMEOUT

    async def search_email(self, email: str) -> dict[str, Any]:
        """
        Search for information about an email using multiple sources

        Args:
            email: Email address to search for

        Returns:
            dict: Combined results from multiple sources
        """
        try:
            logger.info(f"Starting email search for: {email}")

            # Run multiple searches concurrently
            tasks = [
                self._check_haveibeenpwned(email),
                self._check_email_validator(email),
                self._check_domain_info(email),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            combined_result = {
                "email": email,
                "sources": {},
                "summary": {
                    "total_sources": len(tasks),
                    "successful_sources": 0,
                    "failed_sources": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }

            for i, result in enumerate(results):
                source_name = ["haveibeenpwned", "email_validator", "domain_info"][i]

                if isinstance(result, Exception):
                    combined_result["sources"][source_name] = self.format_error(result)
                    combined_result["summary"]["failed_sources"] += 1
                else:
                    combined_result["sources"][source_name] = result
                    combined_result["summary"]["successful_sources"] += 1

            logger.info(f"Email search completed for: {email}")
            return combined_result

        except Exception as e:
            logger.error(f"Error in email search: {e}")
            return self.format_error(e)

    async def _check_haveibeenpwned(self, email: str) -> dict[str, Any]:
        """Check if email has been compromised using HaveIBeenPwned API"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout):
                # Note: This is a mock implementation
                # In reality, you'd use the actual HaveIBeenPwned API
                await asyncio.sleep(0.1)  # Simulate API call

                return {
                    "breached": False,
                    "breach_count": 0,
                    "breaches": [],
                    "source": "haveibeenpwned",
                    "confidence": 0.9,
                }
        except Exception as e:
            logger.error(f"Error checking HaveIBeenPwned: {e}")
            raise

    async def _check_email_validator(self, email: str) -> dict[str, Any]:
        """Validate email format and check if domain exists"""
        try:
            # Basic email validation
            if "@" not in email or "." not in email.split("@")[1]:
                return {
                    "valid": False,
                    "reason": "Invalid email format",
                    "source": "email_validator",
                    "confidence": 1.0,
                }

            domain = email.split("@")[1]

            # Check if domain exists (simplified)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.head(f"https://{domain}")
                    domain_exists = response.status_code < 400
                except Exception:
                    domain_exists = False

            return {
                "valid": True,
                "domain_exists": domain_exists,
                "domain": domain,
                "source": "email_validator",
                "confidence": 0.8,
            }
        except Exception as e:
            logger.error(f"Error validating email: {e}")
            raise

    async def _check_domain_info(self, email: str) -> dict[str, Any]:
        """Get domain information"""
        try:
            domain = email.split("@")[1]

            # Mock domain information
            await asyncio.sleep(0.1)  # Simulate API call

            return {
                "domain": domain,
                "registrar": "Mock Registrar",
                "creation_date": "2020-01-01",
                "expiry_date": "2025-01-01",
                "nameservers": ["ns1.example.com", "ns2.example.com"],
                "source": "domain_info",
                "confidence": 0.7,
            }
        except Exception as e:
            logger.error(f"Error getting domain info: {e}")
            raise
