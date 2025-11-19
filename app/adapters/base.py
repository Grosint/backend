from typing import Any

from app.core.response_mapper import response_mapper


class OSINTAdapter:
    """
    Base adapter interface for all OSINT library adapters.

    Each adapter should implement only the search methods relevant to its domain:
    - EmailAdapter: search_email()
    - DomainAdapter: search_domain()
    - PhoneLookupAdapter: search_phone()
    """

    def __init__(self):
        """Initialize the adapter"""
        self.name = self.__class__.__name__

    def format_error(self, error: Exception) -> dict[str, Any]:
        """
        Format an exception for inclusion in results

        Args:
            error: Exception object

        Returns:
            dict: Formatted error information
        """
        return {"error": str(error), "type": error.__class__.__name__}

    # Enhanced normalization using response mapper system
    def normalize_success_response(
        self, raw_response: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Normalize successful responses using the response mapper system.
        Each adapter can have custom response formatting.
        """
        return response_mapper.map_success_response(self.name, raw_response)

    def normalize_error_response(self, error: Exception) -> dict[str, Any]:
        """
        Normalize error responses using the response mapper system.
        Each adapter can have custom error formatting.
        """
        return response_mapper.map_error_response(self.name, error)
