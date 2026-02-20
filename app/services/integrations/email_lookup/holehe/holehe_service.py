from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.exceptions import ExternalServiceException

logger = logging.getLogger(__name__)

# Response categories constant
RESPONSE_CATEGORIES = {"TEXT": "TEXT"}

# Default response when no data is found
DEFAULT_HOLEHE_RESPONSE = []


def build_holehe_response(data: list[str]) -> list[dict[str, Any]]:
    """
    Build holehe response in the standardized format.

    Args:
        data: List of service names where the email was found

    Returns:
        Formatted response list with twitter shown separately and others in additionalServices
    """
    if len(data) == 0:
        return DEFAULT_HOLEHE_RESPONSE
    formatted_response = []
    for i in data:
        if i == "twitter":
            formatted_response.append(
                {
                    "type": "twitter",
                    "source": "Account Exists",
                    "value": "Yes",
                    "showSource": True,
                    "category": RESPONSE_CATEGORIES["TEXT"],
                }
            )
        else:
            formatted_response.append(
                {
                    "type": "additionalServices",
                    "source": None,
                    "value": i,
                    "showSource": False,
                    "category": RESPONSE_CATEGORIES["TEXT"],
                }
            )
    return formatted_response


class HoleheService:
    """
    Main holehe service that aggregates email lookup results.
    This service checks if an email exists on various websites and platforms.
    """

    def __init__(self):
        self.name = "HoleheService"

    async def search_email(self, email: str) -> dict[str, Any]:
        """
        Main entry point: Search email using holehe.
        This method orchestrates all holehe modules to check email existence.

        Args:
            email: Email address to search for

        Returns:
            dict: Comprehensive results from all holehe sources
        """
        try:
            logger.info(f"Holehe: Starting comprehensive search for {email}")

            # Import holehe core functions
            try:
                from app.externals.holehe.core import maincore
            except ImportError as e:
                logger.error(f"Holehe: Failed to import holehe core: {e}")
                raise ExternalServiceException(
                    service_name="Holehe",
                    message=f"Failed to import holehe library: {str(e)}",
                ) from e

            # Run holehe email search using async methods
            try:
                raw_data, formatted_result = await self._run_holehe_search_async(
                    email, maincore
                )
            except ExternalServiceException:
                # Re-raise external service errors to be handled by outer catch
                raise
            except Exception as e:
                logger.error(f"Holehe: Search execution failed: {e}")
                return {
                    "found": False,
                    "source": "holehe",
                    "data": None,
                    "confidence": 0.0,
                    "error": str(e),
                    "error_code": "SEARCH_ERROR",
                    "_raw_response": {
                        "error": str(e),
                        "exception_type": type(e).__name__,
                    },
                }

            if not raw_data or len(raw_data) == 0:
                return {
                    "found": False,
                    "source": "holehe",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": {"raw_data": raw_data},
                }

            # Extract service names from raw data
            # Raw data contains dicts with "name" field (e.g., "twitter", "github")
            service_names = self._extract_service_names(raw_data)

            if not service_names or len(service_names) == 0:
                return {
                    "found": False,
                    "source": "holehe",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": {"raw_data": raw_data},
                }

            # Format the response
            formatted_data = build_holehe_response(service_names)

            return {
                "found": True,
                "source": "holehe",
                "data": formatted_data,
                "confidence": 0.8 if len(service_names) > 0 else 0.0,
                "_raw_response": {
                    "raw_data": raw_data,
                    "formatted_result": formatted_result,
                    "service_names": service_names,
                },
            }

        except ExternalServiceException as e:
            # Handle external service errors gracefully
            logger.warning(f"Holehe external service error: {e.message}")
            return {
                "found": False,
                "source": "holehe",
                "data": None,
                "confidence": 0.0,
                "error": e.message,
                "error_code": e.error_code,
                "_raw_response": {"error": e.message, "details": e.details},
            }
        except Exception as e:
            logger.error(f"Holehe search failed: {e}")
            return {
                "found": False,
                "source": "holehe",
                "error": str(e),
                "error_code": "SEARCH_ERROR",
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    async def _run_holehe_search_async(
        self, email: str, maincore_func: callable
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Run holehe search asynchronously.

        Args:
            email: Email address to search
            maincore_func: holehe maincore function (not used, but kept for compatibility)

        Returns:
            tuple: (raw_data list of dicts, formatted_result list of strings)
        """
        try:
            logger.debug(f"Holehe: Running async search for {email}")

            # Import holehe internals to get raw data
            import httpx
            import trio

            from app.externals.holehe.core import (
                get_functions,
                import_submodules,
                is_email,
                launch_module,
                print_result,
            )
            from app.externals.holehe.instruments import TrioProgress

            if not is_email(email):
                raise ValueError(f"Invalid email format: {email}")

            # Create a synchronous wrapper function to run in thread
            def run_holehe_search():
                """Synchronous wrapper to run trio code in a thread."""
                # Import Modules
                modules = import_submodules("app.externals.holehe.modules")
                websites = get_functions(modules)

                timeout = 10

                # Limit concurrency to reduce rate limiting (118/121 were rate-limited with all-at-once)
                max_concurrent = 5
                semaphore = trio.Semaphore(max_concurrent)

                # Launching the modules using trio (throttled to avoid rate limits)
                async def run_modules():
                    client = httpx.AsyncClient(timeout=timeout)
                    out = []
                    instrument = TrioProgress(len(websites))

                    async def run_with_limit(website):
                        async with semaphore:
                            try:
                                await launch_module(website, email, client, out)
                            except trio.Cancelled:
                                raise  # Never swallow cancellation
                            except BaseException:
                                # Catch module/launch_module errors so one failing module
                                # doesn't cancel the nursery (ExceptionGroup from 6+ raises)
                                name = getattr(website, "__name__", "unknown")
                                out.append(
                                    {
                                        "name": name,
                                        "domain": f"{name}.com",
                                        "rateLimit": True,
                                        "exists": False,
                                        "emailrecovery": None,
                                        "phoneNumber": None,
                                        "others": None,
                                    }
                                )

                    trio.lowlevel.add_instrument(instrument)
                    try:
                        async with trio.open_nursery() as nursery:
                            for website in websites:
                                nursery.start_soon(run_with_limit, website)
                    except BaseException as nursery_error:
                        if hasattr(nursery_error, "exceptions"):
                            for exc in nursery_error.exceptions:
                                logger.debug(
                                    f"Holehe: Exception in module: {type(exc).__name__}: {exc}"
                                )
                        raise
                    finally:
                        trio.lowlevel.remove_instrument(instrument)

                    # Sort by modules names
                    out = sorted(out, key=lambda i: i.get("name", ""))

                    # Close the client
                    await client.aclose()

                    # Get formatted result using print_result
                    formatted_result = print_result(out, email, websites)

                    return out, formatted_result

                # Run the async trio code
                return trio.run(run_modules)

            # Run the synchronous wrapper in a thread pool
            raw_data, formatted_result = await asyncio.to_thread(run_holehe_search)

            logger.debug(f"Holehe: Search completed for {email}")
            return raw_data, formatted_result
        except Exception as e:
            logger.error(f"Holehe: Error during search execution: {e}")
            raise

    def _extract_service_names(self, raw_data: list[dict[str, Any]]) -> list[str]:
        """
        Extract service names from holehe raw data.

        Raw data contains dictionaries with "name" field (e.g., {"name": "twitter", ...}).
        We extract the service names where "exists" is True.

        Args:
            raw_data: List of dictionaries from holehe with "name" and "exists" fields

        Returns:
            list: List of service names (lowercase)
        """
        service_names = []
        for item in raw_data:
            if isinstance(item, dict):
                exists = item.get("exists", False)
                name = item.get("name")
                if exists and name:
                    # Use the name directly (already lowercase from holehe)
                    service_names.append(name.lower())
        return service_names
