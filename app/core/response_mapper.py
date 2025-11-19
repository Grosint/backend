from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class ResponseMapper:
    """
    Flexible response mapping system for different API response formats.
    Each adapter can define custom mappers for success and error responses.
    """

    def __init__(self):
        self.success_mappers: dict[str, Callable[[dict], dict]] = {}
        self.error_mappers: dict[str, Callable[[Exception], dict]] = {}

    def register_success_mapper(
        self, adapter_name: str, mapper: Callable[[dict], dict]
    ):
        """Register a success response mapper for an adapter"""
        self.success_mappers[adapter_name] = mapper
        logger.debug(f"Registered success mapper for {adapter_name}")

    def register_error_mapper(
        self, adapter_name: str, mapper: Callable[[Exception], dict]
    ):
        """Register an error response mapper for an adapter"""
        self.error_mappers[adapter_name] = mapper
        logger.debug(f"Registered error mapper for {adapter_name}")

    def map_success_response(self, adapter_name: str, raw_response: dict) -> dict:
        """Map a success response using the registered mapper"""
        if adapter_name in self.success_mappers:
            try:
                return self.success_mappers[adapter_name](raw_response)
            except Exception as e:
                logger.error(f"Error in success mapper for {adapter_name}: {e}")
                return self._default_success_mapper(raw_response)
        else:
            return self._default_success_mapper(raw_response)

    def map_error_response(self, adapter_name: str, error: Exception) -> dict:
        """Map an error response using the registered mapper"""
        if adapter_name in self.error_mappers:
            try:
                return self.error_mappers[adapter_name](error)
            except Exception as e:
                logger.error(f"Error in error mapper for {adapter_name}: {e}")
                return self._default_error_mapper(error)
        else:
            return self._default_error_mapper(error)

    def _default_success_mapper(self, raw_response: dict) -> dict:
        """Default success response mapper"""
        return {
            "success": True,
            "message": "Operation completed successfully",
            "data": raw_response,
        }

    def _default_error_mapper(self, error: Exception) -> dict:
        """Default error response mapper"""
        return {
            "success": False,
            "message": str(error),
            "error_code": error.__class__.__name__,
            "data": None,
        }


# Global response mapper instance
response_mapper = ResponseMapper()


# Pre-defined mappers for common API patterns
def social_media_success_mapper(raw_response: dict) -> dict:
    """Mapper for social media API responses"""
    return {
        "success": True,
        "message": "Social media data retrieved successfully",
        "data": {
            "platforms": raw_response.get("platforms", {}),
            "summary": raw_response.get("summary", {}),
            "confidence_score": raw_response.get("summary", {}).get(
                "confidence_score", 0.0
            ),
            "last_updated": raw_response.get("last_updated", "unknown"),
        },
        "metadata": {
            "source_type": "social_media",
            "data_quality": (
                "high"
                if raw_response.get("summary", {}).get("confidence_score", 0) > 0.7
                else "medium"
            ),
        },
    }


def security_success_mapper(raw_response: dict) -> dict:
    """Mapper for security/threat intelligence API responses"""
    return {
        "success": True,
        "message": "Security analysis completed successfully",
        "data": {
            "threat_analysis": raw_response.get("threat_analysis", {}),
            "risk_assessment": raw_response.get("risk_assessment", {}),
            "recommendations": raw_response.get("recommendations", []),
            "confidence_score": 1.0
            - raw_response.get("risk_assessment", {}).get("risk_score", 0.5),
        },
        "metadata": {
            "source_type": "security",
            "threat_level": raw_response.get("risk_assessment", {}).get(
                "overall_risk", "unknown"
            ),
        },
    }


def domain_success_mapper(raw_response: dict) -> dict:
    """Mapper for domain analysis API responses"""
    return {
        "success": True,
        "message": "Domain analysis completed successfully",
        "data": {
            "domain": raw_response.get("domain", "unknown"),
            "sources": raw_response.get("sources", {}),
            "summary": raw_response.get("summary", {}),
            "confidence_score": raw_response.get("summary", {}).get(
                "successful_sources", 0
            )
            / max(raw_response.get("summary", {}).get("total_sources", 1), 1),
        },
        "metadata": {
            "source_type": "domain_analysis",
            "data_completeness": (
                "high"
                if raw_response.get("summary", {}).get("successful_sources", 0) > 2
                else "partial"
            ),
        },
    }


def api_error_mapper(error: Exception) -> dict:
    """Enhanced error mapper with more context"""
    error_type = error.__class__.__name__

    # Map common HTTP errors to user-friendly messages
    if "Timeout" in error_type:
        message = "External API request timed out"
        error_code = "TIMEOUT_ERROR"
    elif "Connection" in error_type:
        message = "Unable to connect to external API"
        error_code = "CONNECTION_ERROR"
    elif "HTTP" in error_type:
        message = "External API returned an error"
        error_code = "HTTP_ERROR"
    else:
        message = f"External API error: {str(error)}"
        error_code = "API_ERROR"

    return {
        "success": False,
        "message": message,
        "error_code": error_code,
        "data": None,
        "metadata": {
            "error_type": error_type,
            "retry_recommended": error_type in ["Timeout", "Connection"],
        },
    }


def phone_lookup_success_mapper(raw_response: dict) -> dict:
    """Mapper for phone lookup API responses"""
    return {
        "success": True,
        "message": "Phone lookup completed successfully",
        "data": {
            "phone": raw_response.get("phone", "unknown"),
            "lookup_results": raw_response.get("lookup_results", {}),
            "summary": raw_response.get("summary", {}),
            "confidence_score": raw_response.get("summary", {}).get(
                "successful_sources", 0
            )
            / max(raw_response.get("summary", {}).get("total_sources", 1), 1),
        },
        "metadata": {
            "source_type": "phone_lookup",
            "data_completeness": (
                "high"
                if raw_response.get("summary", {}).get("found_data", False)
                else "low"
            ),
        },
    }


# Register default mappers
response_mapper.register_success_mapper(
    "SocialMediaAdapter", social_media_success_mapper
)
response_mapper.register_success_mapper("SecurityAdapter", security_success_mapper)
response_mapper.register_success_mapper("DomainAdapter", domain_success_mapper)
response_mapper.register_success_mapper(
    "EmailAdapter", domain_success_mapper
)  # Reuse domain mapper
response_mapper.register_success_mapper(
    "PhoneLookupAdapter", phone_lookup_success_mapper
)

# Register error mappers
response_mapper.register_error_mapper("SocialMediaAdapter", api_error_mapper)
response_mapper.register_error_mapper("SecurityAdapter", api_error_mapper)
response_mapper.register_error_mapper("DomainAdapter", api_error_mapper)
response_mapper.register_error_mapper("EmailAdapter", api_error_mapper)
response_mapper.register_error_mapper("PhoneLookupAdapter", api_error_mapper)
