from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

from app.core.exceptions import ExternalServiceException

logger = logging.getLogger(__name__)


class PhilINTService:
    """
    Main philINT service that aggregates email lookup results.
    This is a blackbox service - takes an email and returns comprehensive results
    from philINT's various sources (Adobe, Chess.com, Duolingo, GitHub, etc.)
    """

    def __init__(self):
        self.name = "PhilINTService"

    async def search_email(self, email: str) -> dict[str, Any]:
        """
        Main entry point: Search email using philINT.
        This is the blackbox method that orchestrates all philINT sources.

        Args:
            email: Email address to search for

        Returns:
            dict: Comprehensive results from all philINT sources
        """
        try:
            logger.info(f"PhilINT: Starting comprehensive search for {email}")

            # Import philINT classes
            try:
                from philINT.classes import Email, Person
            except ImportError as e:
                logger.error(f"PhilINT: Failed to import philINT classes: {e}")
                raise ExternalServiceException(
                    service_name="PhilINT",
                    message=f"Failed to import philINT library: {str(e)}",
                ) from e

            # Run philINT email search using async methods
            try:
                result = await self._run_philint_search_async(email, Email, Person)
            except ExternalServiceException:
                # Re-raise external service errors to be handled by outer catch
                raise
            except OSError as e:
                # Handle DNS/network errors that weren't caught inside
                error_msg = str(e)
                if (
                    "nodename nor servname" in error_msg
                    or "Name or service not known" in error_msg
                ):
                    logger.warning(f"PhilINT: DNS resolution error - {error_msg}")
                    raise ExternalServiceException(
                        service_name="PhilINT",
                        message="Network error: Unable to resolve hostnames. Check internet connection and DNS settings.",
                        details={"error": error_msg, "error_type": "DNS_ERROR"},
                    ) from e
                else:
                    logger.error(f"PhilINT: Network error - {error_msg}")
                    raise ExternalServiceException(
                        service_name="PhilINT",
                        message=f"Network error: {error_msg}",
                        details={"error": error_msg, "error_type": "NETWORK_ERROR"},
                    ) from e
            except Exception as e:
                logger.error(f"PhilINT: Search execution failed: {e}")
                return {
                    "found": False,
                    "source": "philint",
                    "data": None,
                    "confidence": 0.0,
                    "error": str(e),
                    "error_code": "SEARCH_ERROR",
                    "_raw_response": {
                        "error": str(e),
                        "exception_type": type(e).__name__,
                    },
                }

            if not result or not result.get("found"):
                return {
                    "found": False,
                    "source": "philint",
                    "data": None,
                    "confidence": 0.0,
                    "_raw_response": result.get("_raw_response", {}),
                }

            # Format the response
            formatted_data = self._format_email_response(result, email)

            return {
                "found": True,
                "source": "philint",
                "data": formatted_data,
                "confidence": 0.8,
                "_raw_response": result.get("_raw_response", {}),
            }

        except ExternalServiceException as e:
            # Handle external service errors (like DNS/network errors) gracefully
            # Log as warning since these are expected network issues, not code errors
            logger.warning(f"PhilINT external service error: {e.message}")
            if e.details and e.details.get("failed_hostname"):
                logger.info(
                    f"PhilINT: Failed to resolve hostname: {e.details.get('failed_hostname')}"
                )
            return {
                "found": False,
                "source": "philint",
                "data": None,
                "confidence": 0.0,
                "error": e.message,
                "error_code": e.error_code,
                "_raw_response": {"error": e.message, "details": e.details},
            }
        except Exception as e:
            logger.error(f"PhilINT search failed: {e}")
            return {
                "found": False,
                "source": "philint",
                "error": str(e),
                "error_code": "SEARCH_ERROR",
                "_raw_response": {"error": str(e), "exception_type": type(e).__name__},
            }

    async def _run_philint_search_async(
        self, email: str, EmailClass: type, PersonClass: type
    ) -> dict[str, Any]:
        """
        Run philINT search asynchronously using async methods.

        Args:
            email: Email address to search
            EmailClass: philINT.classes.Email class
            PersonClass: philINT.classes.Person class

        Returns:
            dict: Raw philINT results
        """
        try:
            # Create Email object
            email_obj = EmailClass(email)

            # Use async method if available, otherwise fall back to sync
            email_search_error = None
            try:
                if hasattr(email_obj, "run_all_coro"):
                    logger.debug(f"PhilINT: Running async email search for {email}")
                    await email_obj.run_all_coro()
                    logger.debug(f"PhilINT: Email search completed for {email}")
                else:
                    # If no async method, run sync version in thread pool with new event loop
                    logger.debug(
                        f"PhilINT: Running sync email search in thread for {email}"
                    )
                    await asyncio.to_thread(self._run_philint_sync_with_loop, email_obj)
                    logger.debug(f"PhilINT: Sync email search completed for {email}")
            except (OSError, socket.gaierror) as e:
                # Catch DNS/network errors from email search
                # Don't fail completely - continue to extract whatever data we can
                error_msg = str(e)
                error_args = getattr(e, "args", [])
                hostname = error_args[1] if len(error_args) > 1 else "unknown"
                email_search_error = {
                    "error": error_msg,
                    "error_type": (
                        "DNS_ERROR"
                        if "nodename nor servname" in error_msg
                        or "Name or service not known" in error_msg
                        else "NETWORK_ERROR"
                    ),
                    "failed_hostname": str(hostname),
                }
                logger.warning(
                    f"PhilINT: Network error during email search - {error_msg}. "
                    f"Failed hostname: {hostname}. Continuing with partial results..."
                )
                # Continue execution to extract whatever data philINT managed to collect
            except Exception as e:
                # Catch any other errors but continue
                error_msg = str(e)
                email_search_error = {
                    "error": error_msg,
                    "error_type": type(e).__name__,
                }
                logger.warning(
                    f"PhilINT: Error during email search - {error_msg}. Continuing with partial results..."
                )

            # Create Person object and fill from email
            target_person = PersonClass()

            # Check if fill_from_email has async version
            try:
                if hasattr(target_person, "fill_from_email_coro"):
                    await target_person.fill_from_email_coro(email_obj)
                else:
                    # Run sync version in thread pool with event loop (may need async internally)
                    await asyncio.to_thread(
                        self._fill_person_from_email, target_person, email_obj
                    )
            except (OSError, socket.gaierror) as e:
                # Catch DNS/network errors from person fill
                error_msg = str(e)
                logger.warning(
                    f"PhilINT: Network error during person fill - {error_msg}"
                )
                # Continue with partial data if email search succeeded
                pass

            # Extract raw data (even if there were errors, extract what we can)
            logger.debug(f"PhilINT: Extracting raw data for {email}")
            try:
                raw_data = self._extract_raw_data(email_obj, target_person)
                logger.debug(f"PhilINT: Raw data extracted successfully for {email}")
            except Exception as e:
                logger.error(
                    f"PhilINT: Error extracting raw data for {email}: {e}",
                    exc_info=True,
                )
                # Return empty data structure if extraction fails
                raw_data = {
                    "email": email,
                    "email_data": {},
                    "person_data": {},
                    "extraction_error": str(e),
                }

            # Add error information if there were errors
            if email_search_error:
                raw_data["email_search_error"] = email_search_error

            # Check if any data was found
            logger.debug(f"PhilINT: Checking if data was found for {email}")
            found = self._check_if_found(raw_data)
            logger.debug(f"PhilINT: Data found: {found} for {email}")

            # If we had errors but found some data, still return success with partial data
            if email_search_error and found:
                logger.info(
                    f"PhilINT: Found partial data despite network errors for {email}"
                )
                return {
                    "found": True,
                    "source": "philint",
                    "data": self._format_email_response(
                        {"found": found, "_raw_response": raw_data}, email
                    ),
                    "confidence": 0.6,  # Lower confidence for partial data
                    "_raw_response": raw_data,
                    "partial": True,
                    "warning": f"Some services failed: {email_search_error.get('failed_hostname', 'unknown')}",
                }

            # If we had errors and no data, return not found with error info
            if email_search_error and not found:
                logger.warning(
                    f"PhilINT: No data found and had network errors for {email}"
                )
                raise ExternalServiceException(
                    service_name="PhilINT",
                    message=f"Network error: Unable to resolve hostname '{email_search_error.get('failed_hostname', 'unknown')}'. No data could be retrieved.",
                    details=email_search_error,
                )

            # Format the response
            logger.debug(f"PhilINT: Formatting response for {email}")
            formatted_data = self._format_email_response(
                {"found": found, "_raw_response": raw_data}, email
            )
            logger.debug(f"PhilINT: Response formatted, found: {found} for {email}")

            return {
                "found": found,
                "source": "philint",
                "data": formatted_data,
                "confidence": 0.8 if found else 0.0,
                "_raw_response": raw_data,
            }

        except ExternalServiceException:
            # Re-raise external service exceptions (already properly formatted)
            raise
        except (OSError, socket.gaierror) as e:
            # Handle DNS/network errors gracefully (catch-all for any that weren't caught above)
            error_msg = str(e)
            error_args = getattr(e, "args", [])
            hostname = error_args[1] if len(error_args) > 1 else "unknown"

            if (
                "nodename nor servname" in error_msg
                or "Name or service not known" in error_msg
            ):
                logger.warning(
                    f"PhilINT: DNS resolution error - {error_msg}. "
                    f"Failed hostname: {hostname}"
                )
                raise ExternalServiceException(
                    service_name="PhilINT",
                    message=f"Network error: Unable to resolve hostname '{hostname}'. Some philINT services may be unavailable.",
                    details={
                        "error": error_msg,
                        "error_type": "DNS_ERROR",
                        "failed_hostname": str(hostname),
                    },
                ) from e
            else:
                logger.warning(f"PhilINT: Network error during search execution: {e}")
                raise ExternalServiceException(
                    service_name="PhilINT",
                    message=f"Network error: {error_msg}",
                    details={"error": error_msg, "error_type": "NETWORK_ERROR"},
                ) from e
        except Exception as e:
            # Check if the exception contains a DNS/network error
            error_msg = str(e)
            error_type = type(e).__name__

            # Check for DNS errors in wrapped exceptions
            if (
                "nodename nor servname" in error_msg
                or "Name or service not known" in error_msg
                or "gaierror" in error_type.lower()
            ):
                # Try to extract hostname from error if possible
                hostname = "unknown"
                if hasattr(e, "args") and len(e.args) > 1:
                    hostname = str(e.args[1])
                elif "(" in error_msg and ")" in error_msg:
                    # Try to extract hostname from error message
                    try:
                        parts = error_msg.split("(")
                        if len(parts) > 1:
                            hostname = parts[-1].rstrip(")")
                    except Exception:  # nosec B110
                        pass

                logger.warning(
                    f"PhilINT: DNS resolution error (wrapped) - {error_msg}. "
                    f"Failed hostname: {hostname}"
                )
                raise ExternalServiceException(
                    service_name="PhilINT",
                    message=f"Network error: Unable to resolve hostname '{hostname}'. Some philINT services may be unavailable.",
                    details={
                        "error": error_msg,
                        "error_type": "DNS_ERROR",
                        "wrapped": True,
                        "failed_hostname": hostname,
                    },
                ) from e

            logger.error(f"PhilINT: Error during search execution: {e}")
            raise

    def _run_philint_sync_with_loop(self, email_obj: Any) -> None:
        """
        Run philINT sync method in a thread with a new event loop.
        This is a fallback when async methods are not available.

        Args:
            email_obj: philINT Email object
        """
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            email_obj.run_all()
        except OSError:
            # Re-raise DNS/network errors so they can be handled by the caller
            raise
        finally:
            loop.close()

    def _fill_person_from_email(self, person_obj: Any, email_obj: Any) -> None:
        """
        Fill Person object from Email object in a thread with event loop.
        This ensures async operations inside fill_from_email have an event loop.

        Args:
            person_obj: philINT Person object
            email_obj: philINT Email object
        """
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            person_obj.fill_from_email(email_obj)
        except OSError:
            # Re-raise DNS/network errors so they can be handled by the caller
            raise
        finally:
            loop.close()

    def _extract_raw_data(self, email_obj: Any, person_obj: Any) -> dict[str, Any]:
        """
        Extract raw data from philINT Email and Person objects.

        Args:
            email_obj: philINT Email object
            person_obj: philINT Person object

        Returns:
            dict: Extracted raw data
        """
        logger.debug("PhilINT: Starting raw data extraction")
        raw_data = {
            "email": getattr(email_obj, "email", None),
            "email_data": {},
            "person_data": {},
        }

        # Extract email object attributes
        logger.debug("PhilINT: Extracting email object attributes")
        try:
            if hasattr(email_obj, "spam"):
                raw_data["email_data"]["spam"] = email_obj.spam
            if hasattr(email_obj, "deliverable"):
                raw_data["email_data"]["deliverable"] = email_obj.deliverable
            if hasattr(email_obj, "disposable"):
                raw_data["email_data"]["disposable"] = email_obj.disposable
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting email attributes: {e}")

        # Extract person object attributes
        # Based on philINT documentation, Person object has:
        # - email_addresses
        # - usernames
        # - names
        # - pictures
        # - accounts
        logger.debug("PhilINT: Extracting person object attributes")

        try:
            if hasattr(person_obj, "email_addresses"):
                email_addresses = getattr(person_obj, "email_addresses", None)
                if email_addresses is not None:
                    try:
                        raw_data["person_data"]["email_addresses"] = list(
                            email_addresses
                        )
                    except (TypeError, ValueError) as e:
                        logger.warning(
                            f"PhilINT: Error converting email_addresses to list: {e}"
                        )
                        raw_data["person_data"]["email_addresses"] = []
                else:
                    raw_data["person_data"]["email_addresses"] = []
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting email_addresses: {e}")
            raw_data["person_data"]["email_addresses"] = []

        try:
            if hasattr(person_obj, "usernames"):
                usernames = getattr(person_obj, "usernames", None)
                if usernames is not None:
                    try:
                        raw_data["person_data"]["usernames"] = list(usernames)
                    except (TypeError, ValueError) as e:
                        logger.warning(
                            f"PhilINT: Error converting usernames to list: {e}"
                        )
                        raw_data["person_data"]["usernames"] = []
                else:
                    raw_data["person_data"]["usernames"] = []
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting usernames: {e}")
            raw_data["person_data"]["usernames"] = []

        try:
            if hasattr(person_obj, "names"):
                names = getattr(person_obj, "names", None)
                if names is not None:
                    try:
                        raw_data["person_data"]["names"] = list(names)
                    except (TypeError, ValueError) as e:
                        logger.warning(f"PhilINT: Error converting names to list: {e}")
                        raw_data["person_data"]["names"] = []
                else:
                    raw_data["person_data"]["names"] = []
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting names: {e}")
            raw_data["person_data"]["names"] = []

        try:
            if hasattr(person_obj, "pictures"):
                pictures = getattr(person_obj, "pictures", None)
                if pictures is not None:
                    try:
                        raw_data["person_data"]["pictures"] = list(pictures)
                    except (TypeError, ValueError) as e:
                        logger.warning(
                            f"PhilINT: Error converting pictures to list: {e}"
                        )
                        raw_data["person_data"]["pictures"] = []
                else:
                    raw_data["person_data"]["pictures"] = []
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting pictures: {e}")
            raw_data["person_data"]["pictures"] = []

        try:
            if hasattr(person_obj, "accounts"):
                accounts = getattr(person_obj, "accounts", None)
                if accounts is not None:
                    try:
                        raw_data["person_data"]["accounts"] = list(accounts)
                    except (TypeError, ValueError) as e:
                        logger.warning(
                            f"PhilINT: Error converting accounts to list: {e}"
                        )
                        raw_data["person_data"]["accounts"] = []
                else:
                    raw_data["person_data"]["accounts"] = []
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting accounts: {e}")
            raw_data["person_data"]["accounts"] = []

        # Try to get display_raw_data if available
        try:
            if hasattr(person_obj, "display_raw_data"):
                # This might return a dict or string, handle both
                raw_display = person_obj.display_raw_data()
                if isinstance(raw_display, dict):
                    raw_data["person_data"]["raw_display"] = raw_display
        except Exception as e:
            logger.debug(f"Could not get display_raw_data: {e}")

        logger.debug(
            f"PhilINT: Raw data extraction completed. Keys: {list(raw_data.keys())}"
        )
        return raw_data

    def _check_if_found(self, raw_data: dict[str, Any]) -> bool:
        """
        Check if any meaningful data was found.

        Args:
            raw_data: Raw data dictionary

        Returns:
            bool: True if data was found
        """
        person_data = raw_data.get("person_data", {})

        # Check if any person data exists
        if (
            person_data.get("email_addresses")
            or person_data.get("usernames")
            or person_data.get("names")
            or person_data.get("pictures")
            or person_data.get("accounts")
        ):
            return True

        # Check email data
        email_data = raw_data.get("email_data", {})
        return bool(email_data)

    def _format_email_response(
        self, result: dict[str, Any] | None, email: str
    ) -> list[dict]:
        """Format philINT email response to standard format following coding standards"""
        logger.debug(f"PhilINT: Formatting email response for {email}")
        formatted_response = []

        if not result:
            logger.debug("PhilINT: No result to format")
            return formatted_response

        raw_data = result.get("_raw_response", {})
        if not raw_data:
            logger.debug("PhilINT: No raw_data in result")
            return formatted_response

        person_data = raw_data.get("person_data", {}) or {}
        email_data = raw_data.get("email_data", {}) or {}

        # Extract names
        try:
            names = person_data.get("names")
            if names is not None:
                if not isinstance(names, (list, tuple, set)):
                    logger.warning(
                        f"PhilINT: names is not iterable, type: {type(names)}"
                    )
                    names = []
                else:
                    names = list(names)
            else:
                names = []

            if names:
                logger.debug(f"PhilINT: Processing {len(names)} names")
                for name in names:
                    if name:
                        formatted_response.append(
                            {
                                "type": "name",
                                "source": "philint",
                                "value": str(name),
                                "showSource": False,
                                "category": "TEXT",
                            }
                        )
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting names: {e}")

        # Extract email addresses
        try:
            email_addresses = person_data.get("email_addresses")
            if email_addresses is not None:
                if not isinstance(email_addresses, (list, tuple, set)):
                    logger.warning(
                        f"PhilINT: email_addresses is not iterable, type: {type(email_addresses)}"
                    )
                    email_addresses = []
                else:
                    email_addresses = list(email_addresses)
            else:
                email_addresses = []

            if email_addresses:
                logger.debug(
                    f"PhilINT: Processing {len(email_addresses)} email addresses"
                )
                for email_addr in email_addresses:
                    if (
                        email_addr and email_addr != email
                    ):  # Don't duplicate the search email
                        formatted_response.append(
                            {
                                "type": "email",
                                "source": "philint",
                                "value": str(email_addr),
                                "showSource": False,
                                "category": "TEXT",
                            }
                        )
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting email addresses: {e}")

        # Extract usernames
        try:
            usernames = person_data.get("usernames")
            if usernames is not None:
                if not isinstance(usernames, (list, tuple, set)):
                    logger.warning(
                        f"PhilINT: usernames is not iterable, type: {type(usernames)}"
                    )
                    usernames = []
                else:
                    usernames = list(usernames)
            else:
                usernames = []

            if usernames:
                logger.debug(f"PhilINT: Processing {len(usernames)} usernames")
                for username in usernames:
                    if username:
                        formatted_response.append(
                            {
                                "type": "username",
                                "source": "philint",
                                "value": str(username),
                                "showSource": False,
                                "category": "TEXT",
                            }
                        )
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting usernames: {e}")

        # Extract pictures/images
        try:
            pictures = person_data.get("pictures")
            if pictures is not None:
                if not isinstance(pictures, (list, tuple, set)):
                    logger.warning(
                        f"PhilINT: pictures is not iterable, type: {type(pictures)}"
                    )
                    pictures = []
                else:
                    pictures = list(pictures)
            else:
                pictures = []

            if pictures:
                logger.debug(f"PhilINT: Processing {len(pictures)} pictures")
                for picture_url in pictures:
                    if picture_url:
                        formatted_response.append(
                            {
                                "type": "image",
                                "source": "philint",
                                "value": str(picture_url),
                                "showSource": False,
                                "category": "IMAGE",
                            }
                        )
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting pictures: {e}")

        # Extract accounts (platforms where the email was found)
        try:
            accounts = person_data.get("accounts")
            if accounts is not None:
                if not isinstance(accounts, (list, tuple, set)):
                    logger.warning(
                        f"PhilINT: accounts is not iterable, type: {type(accounts)}"
                    )
                    accounts = []
                else:
                    accounts = list(accounts)
            else:
                accounts = []

            if accounts:
                logger.debug(f"PhilINT: Processing {len(accounts)} accounts")
                for account in accounts:
                    if account:
                        formatted_response.append(
                            {
                                "type": "account",
                                "source": "philint",
                                "value": str(account),
                                "showSource": False,
                                "category": "TEXT",
                            }
                        )
        except Exception as e:
            logger.warning(f"PhilINT: Error extracting accounts: {e}")

        # Add email metadata if available
        if email_data:
            if email_data.get("spam") is not None:
                formatted_response.append(
                    {
                        "type": "emailMetadata",
                        "source": "philint",
                        "value": f"Spam: {email_data.get('spam')}",
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
            if email_data.get("deliverable") is not None:
                formatted_response.append(
                    {
                        "type": "emailMetadata",
                        "source": "philint",
                        "value": f"Deliverable: {email_data.get('deliverable')}",
                        "showSource": False,
                        "category": "TEXT",
                    }
                )
            if email_data.get("disposable") is not None:
                formatted_response.append(
                    {
                        "type": "emailMetadata",
                        "source": "philint",
                        "value": f"Disposable: {email_data.get('disposable')}",
                        "showSource": False,
                        "category": "TEXT",
                    }
                )

        return formatted_response
