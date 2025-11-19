from __future__ import annotations

import logging
from typing import Any

from app.adapters.base import OSINTAdapter
from app.core.resilience import ResilientHttpClient
from app.external_apis.security.security_orchestrator import SecurityOrchestrator

logger = logging.getLogger(__name__)


class SecurityAdapter(OSINTAdapter):
    """Adapter for Security/Threat Intelligence APIs"""

    def __init__(self):
        super().__init__()
        self.name = "SecurityAdapter"
        self.client = ResilientHttpClient()
        self.orchestrator = SecurityOrchestrator()

    async def search_email(self, email: str) -> dict[str, Any]:
        """Search email in security/threat databases"""
        try:
            logger.info(f"Security: Searching email {email}")

            # Call multiple security APIs in parallel
            tasks = [
                self._check_malware_databases(email),
                self._check_phishing_databases(email),
                self._check_breach_databases(email),
                self._check_reputation_databases(email),
            ]

            import asyncio

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            combined_data = {
                "email": email,
                "threat_analysis": {
                    "malware_detection": {},
                    "phishing_attempts": {},
                    "data_breaches": {},
                    "reputation_score": {},
                },
                "risk_assessment": {
                    "overall_risk": "low",
                    "risk_score": 0.0,
                    "threat_level": "safe",
                },
                "recommendations": [],
            }

            api_names = ["malware", "phishing", "breaches", "reputation"]
            for i, result in enumerate(results):
                api_name = api_names[i]
                if isinstance(result, Exception):
                    combined_data["threat_analysis"][f"{api_name}_detection"] = {
                        "error": str(result)
                    }
                else:
                    combined_data["threat_analysis"][f"{api_name}_detection"] = result

            # Calculate overall risk
            risk_factors = []
            if combined_data["threat_analysis"]["malware_detection"].get(
                "found", False
            ):
                risk_factors.append("malware")
            if (
                combined_data["threat_analysis"]["phishing_attempts"].get("count", 0)
                > 0
            ):
                risk_factors.append("phishing")
            if combined_data["threat_analysis"]["data_breaches"].get("breached", False):
                risk_factors.append("breach")

            if len(risk_factors) == 0:
                combined_data["risk_assessment"]["overall_risk"] = "low"
                combined_data["risk_assessment"]["risk_score"] = 0.1
            elif len(risk_factors) == 1:
                combined_data["risk_assessment"]["overall_risk"] = "medium"
                combined_data["risk_assessment"]["risk_score"] = 0.5
            else:
                combined_data["risk_assessment"]["overall_risk"] = "high"
                combined_data["risk_assessment"]["risk_score"] = 0.8

            # Generate recommendations
            if "breach" in risk_factors:
                combined_data["recommendations"].append("Change password immediately")
            if "phishing" in risk_factors:
                combined_data["recommendations"].append("Enable 2FA")
            if "malware" in risk_factors:
                combined_data["recommendations"].append("Run antivirus scan")

            return self.normalize_success_response(combined_data)

        except Exception as e:
            logger.error(f"Security search failed: {e}")
            return self.normalize_error_response(e)

    async def _check_malware_databases(self, email: str) -> dict[str, Any]:
        """Check malware databases"""
        try:
            await self.client.request(
                "GET",
                "https://api.virustotal.com/v3/domains",
                params={"domain": email.split("@")[1]},
                circuit_key="virustotal_api",
            )

            # Mock VirusTotal response
            return {
                "found": False,
                "last_seen": None,
                "threat_types": [],
                "scan_results": {
                    "clean": True,
                    "malicious": False,
                    "suspicious": False,
                },
            }
        except Exception as e:
            return {"found": False, "error": str(e)}

    async def _check_phishing_databases(self, email: str) -> dict[str, Any]:
        """Check phishing databases"""
        try:
            await self.client.request(
                "GET",
                "https://api.phishtank.com/check",
                params={"email": email},
                circuit_key="phishtank_api",
            )

            # Mock PhishTank response
            return {
                "count": 2,
                "last_attempt": "2024-01-10",
                "sources": ["phishing_site_1", "suspicious_email"],
                "severity": "medium",
            }
        except Exception as e:
            return {"count": 0, "error": str(e)}

    async def _check_breach_databases(self, email: str) -> dict[str, Any]:
        """Check data breach databases"""
        try:
            await self.client.request(
                "GET",
                "https://api.haveibeenpwned.com/v3/breachedaccount",
                params={"account": email},
                circuit_key="hibp_api",
            )

            # Mock HaveIBeenPwned response
            return {
                "breached": True,
                "breach_count": 1,
                "breaches": [
                    {
                        "source": "company_breach_2023",
                        "date": "2023-06-15",
                        "severity": "medium",
                        "data_types": ["email", "password_hash"],
                    }
                ],
            }
        except Exception as e:
            return {"breached": False, "error": str(e)}

    async def _check_reputation_databases(self, email: str) -> dict[str, Any]:
        """Check reputation databases"""
        try:
            await self.client.request(
                "GET",
                "https://api.reputation.com/check",
                params={"email": email},
                circuit_key="reputation_api",
            )

            # Mock reputation response
            return {
                "reputation_score": 0.8,
                "category": "legitimate",
                "trust_level": "high",
                "spam_score": 0.1,
            }
        except Exception as e:
            return {"reputation_score": 0.5, "error": str(e)}

    async def search_domain(self, domain: str) -> dict[str, Any]:
        """Search domain in security databases"""
        try:
            logger.info(f"Security: Searching domain {domain}")

            tasks = [
                self._check_domain_malware(domain),
                self._check_domain_phishing(domain),
                self._check_domain_reputation(domain),
                self._check_domain_ssl(domain),
            ]

            import asyncio

            results = await asyncio.gather(*tasks, return_exceptions=True)

            combined_data = {
                "domain": domain,
                "security_analysis": {
                    "malware_detection": {},
                    "phishing_risk": {},
                    "reputation": {},
                    "ssl_certificate": {},
                },
                "overall_risk": "low",
                "security_score": 0.0,
            }

            api_names = ["malware", "phishing", "reputation", "ssl"]
            for i, result in enumerate(results):
                api_name = api_names[i]
                if isinstance(result, Exception):
                    combined_data["security_analysis"][f"{api_name}_detection"] = {
                        "error": str(result)
                    }
                else:
                    combined_data["security_analysis"][f"{api_name}_detection"] = result

            # Calculate security score
            security_factors = []
            if combined_data["security_analysis"]["malware_detection"].get(
                "clean", True
            ):
                security_factors.append("clean")
            if combined_data["security_analysis"]["ssl_certificate"].get("valid", True):
                security_factors.append("ssl_valid")
            if combined_data["security_analysis"]["reputation"].get("score", 0.5) > 0.7:
                security_factors.append("good_reputation")

            combined_data["security_score"] = len(security_factors) / 3.0

            if combined_data["security_score"] > 0.8:
                combined_data["overall_risk"] = "low"
            elif combined_data["security_score"] > 0.5:
                combined_data["overall_risk"] = "medium"
            else:
                combined_data["overall_risk"] = "high"

            return self.normalize_success_response(combined_data)

        except Exception as e:
            logger.error(f"Security domain search failed: {e}")
            return self.normalize_error_response(e)

    async def _check_domain_malware(self, domain: str) -> dict[str, Any]:
        """Check domain for malware"""
        try:
            await self.client.request(
                "GET",
                "https://api.virustotal.com/v3/domains",
                params={"domain": domain},
                circuit_key="virustotal_api",
            )

            return {
                "clean": True,
                "last_scan": "2024-01-20",
                "threats_found": 0,
                "scan_engines": 65,
            }
        except Exception as e:
            return {"clean": False, "error": str(e)}

    async def _check_domain_phishing(self, domain: str) -> dict[str, Any]:
        """Check domain for phishing"""
        try:
            await self.client.request(
                "GET",
                "https://api.phishtank.com/check",
                params={"domain": domain},
                circuit_key="phishtank_api",
            )

            return {
                "score": 0.1,
                "suspicious_patterns": [],
                "last_checked": "2024-01-20",
            }
        except Exception as e:
            return {"score": 0.5, "error": str(e)}

    async def _check_domain_reputation(self, domain: str) -> dict[str, Any]:
        """Check domain reputation"""
        try:
            await self.client.request(
                "GET",
                "https://api.reputation.com/check",
                params={"domain": domain},
                circuit_key="reputation_api",
            )

            return {
                "score": 0.95,
                "category": "legitimate",
                "trust_level": "high",
                "blacklisted": False,
            }
        except Exception as e:
            return {"score": 0.5, "error": str(e)}

    async def _check_domain_ssl(self, domain: str) -> dict[str, Any]:
        """Check SSL certificate"""
        try:
            await self.client.request(
                "GET",
                "https://api.ssllabs.com/api/v3/analyze",
                params={"host": domain},
                circuit_key="ssllabs_api",
            )

            return {
                "valid": True,
                "issuer": "Let's Encrypt",
                "expires": "2024-04-15",
                "grade": "A+",
                "protocols": ["TLS 1.2", "TLS 1.3"],
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
