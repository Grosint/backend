from abc import ABC, abstractmethod
from typing import Any


class OSINTAdapter(ABC):
    """
    Base adapter interface for all OSINT library adapters
    """

    def __init__(self):
        self.name = self.__class__.__name__

    @abstractmethod
    async def search_email(self, email: str) -> dict[str, Any]:
        """
        Search for information about an email

        Args:
            email: Email address to search for

        Returns:
            dict: Results from this OSINT source
        """
        pass

    def format_error(self, error: Exception) -> dict[str, Any]:
        """
        Format an exception for inclusion in results

        Args:
            error: Exception object

        Returns:
            dict: Formatted error information
        """
        return {"error": str(error), "type": error.__class__.__name__}
