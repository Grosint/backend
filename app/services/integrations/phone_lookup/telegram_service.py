from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from telethon import TelegramClient, functions
from telethon.errors import (
    FloodWaitError,
    PhoneNumberInvalidError,
    UserDeactivatedError,
)
from telethon.tl import types

from app.core.config import settings

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for Telegram API integration"""

    def __init__(self):
        self.name = "TelegramService"
        self.max_accounts = settings.TELEGRAM_MAX_ACCOUNTS
        self.max_retries = settings.RETRY_MAX_ATTEMPTS
        self.timeout_seconds = settings.EXTERNAL_API_TIMEOUT

    def _get_random_account_config(self) -> tuple[str, str, str] | None:
        """Get random Telegram account configuration"""
        try:
            # Get a random account number (1 to max_accounts)
            account_num = random.randint(1, self.max_accounts)  # nosec B311

            # Get configuration for this account
            api_id = getattr(settings, f"TELEGRAM_API_ID_{account_num}", "")
            api_hash = getattr(settings, f"TELEGRAM_API_HASH_{account_num}", "")
            auth_mobile = getattr(settings, f"TELEGRAM_AUTH_MOBILE_{account_num}", "")

            if not api_id or not api_hash or not auth_mobile:
                logger.warning(
                    f"Telegram account {account_num} not configured, trying other accounts"
                )
                # Try to find any configured account
                for i in range(1, self.max_accounts + 1):
                    api_id = getattr(settings, f"TELEGRAM_API_ID_{i}", "")
                    api_hash = getattr(settings, f"TELEGRAM_API_HASH_{i}", "")
                    auth_mobile = getattr(settings, f"TELEGRAM_AUTH_MOBILE_{i}", "")
                    if api_id and api_hash and auth_mobile:
                        return (api_id, api_hash, auth_mobile)
                return None

            return (api_id, api_hash, auth_mobile)
        except Exception as e:
            logger.error(f"Error getting Telegram account config: {e}")
            return None

    def _get_human_readable_user_status(self, status: types.TypeUserStatus) -> str:
        """Convert Telegram user status to human-readable string"""
        if isinstance(status, types.UserStatusOnline):
            return "Currently online"
        elif isinstance(status, types.UserStatusOffline):
            return status.was_online.strftime("%Y-%m-%d %H:%M:%S %Z")
        elif isinstance(status, types.UserStatusRecently):
            return "Last seen recently"
        elif isinstance(status, types.UserStatusLastWeek):
            return "Last seen last week"
        elif isinstance(status, types.UserStatusLastMonth):
            return "Last seen last month"
        else:
            return "Unknown"

    async def _login(
        self, api_id: str, api_hash: str, api_phone_number: str
    ) -> TelegramClient:
        """Login to Telegram client with timeout and retry logic"""
        client = TelegramClient(api_phone_number, api_id, api_hash)

        try:
            # Connect with timeout
            await asyncio.wait_for(client.connect(), timeout=self.timeout_seconds)

            if not await client.is_user_authorized():
                logger.warning(
                    f"Telegram client for {api_phone_number} is not authorized. "
                    "Session file may be missing or invalid."
                )
                # In production, sessions should be pre-authorized
                # For now, we'll raise an error if not authorized
                await client.disconnect()
                raise ValueError(
                    f"Telegram client for {api_phone_number} is not authorized. "
                    "Please ensure session files are properly configured."
                )

            return client
        except TimeoutError:
            await client.disconnect()
            raise TimeoutError(
                f"Telegram connection timeout after {self.timeout_seconds}s"
            ) from None
        except Exception:
            await client.disconnect()
            raise

    async def _get_user_data(
        self, client: TelegramClient, phone: str
    ) -> dict[str, Any] | None:
        """Get user data from Telegram by phone number with retry logic"""
        attempt = 0
        last_exception = None

        while attempt < self.max_retries:
            attempt += 1
            try:
                # Create a contact
                contact = types.InputPhoneContact(
                    client_id=0, phone=phone, first_name="", last_name=""
                )

                # Attempt to add the contact from the address book with timeout
                contacts = await asyncio.wait_for(
                    client(functions.contacts.ImportContactsRequest([contact])),
                    timeout=self.timeout_seconds,
                )

                users = contacts.users
                number_of_matches = len(users)

                if number_of_matches == 0:
                    return None
                elif number_of_matches == 1:
                    user = users[0]
                    # Delete the contact we just added
                    await asyncio.wait_for(
                        client(functions.contacts.DeleteContactsRequest(id=[user.id])),
                        timeout=self.timeout_seconds,
                    )

                    result = {
                        "Id": user.id,
                        "Username": user.username,
                        "Usernames": user.usernames,
                        "First Name": user.first_name,
                        "Last Name": user.last_name,
                        "Fake": user.fake,
                        "Verified": user.verified,
                        "Premium": user.premium,
                        "Bot": user.bot,
                        "Bot Chat History": user.bot_chat_history,
                        "Restricted": user.restricted,
                        "Restriction Reason": user.restriction_reason,
                        "User Was Online": self._get_human_readable_user_status(
                            user.status
                        ),
                        "Phone": user.phone,
                        "profile_photo": None,  # S3 upload removed as per requirements
                    }

                    return result
                else:
                    # Multiple matches - unexpected, return None
                    logger.warning(
                        f"Multiple matches found for phone {phone}, returning None"
                    )
                    return None

            except FloodWaitError as e:
                # Telegram rate limiting - wait and retry
                wait_time = e.seconds
                logger.warning(
                    f"Telegram FloodWait: waiting {wait_time}s before retry (attempt {attempt}/{self.max_retries})"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(wait_time)
                    continue
                last_exception = e
                break

            except (PhoneNumberInvalidError, UserDeactivatedError) as e:
                # Non-retryable errors
                logger.error(f"Telegram non-retryable error: {e}")
                return None

            except TimeoutError:
                logger.warning(
                    f"Telegram request timeout (attempt {attempt}/{self.max_retries})"
                )
                if attempt < self.max_retries:
                    # Exponential backoff
                    backoff = settings.RETRY_INITIAL_BACKOFF_SECONDS * (
                        settings.RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)
                    )
                    await asyncio.sleep(backoff)
                    continue
                last_exception = TimeoutError(
                    f"Telegram request timeout after {self.max_retries} attempts"
                )
                break

            except TypeError as e:
                logger.error(f"TypeError in _get_user_data: {e}")
                return None

            except Exception as e:
                logger.warning(
                    f"Telegram request error (attempt {attempt}/{self.max_retries}): {e}"
                )
                last_exception = e
                if attempt < self.max_retries:
                    # Exponential backoff
                    backoff = settings.RETRY_INITIAL_BACKOFF_SECONDS * (
                        settings.RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)
                    )
                    await asyncio.sleep(backoff)
                    continue
                break

        # All retries exhausted
        if last_exception:
            logger.error(
                f"Telegram _get_user_data failed after {self.max_retries} attempts: {last_exception}"
            )
        return None

    def _check_for_tg_values(self, value: Any) -> str:
        """Convert Telegram boolean/None values to readable strings"""
        if value is False:
            return "No"
        elif value is True:
            return "Yes"
        elif value is None:
            return "Not Available"
        else:
            return str(value)

    def _format_response(
        self, data: dict[str, Any] | None, is_error: bool = False
    ) -> list[dict[str, Any]]:
        """Format Telegram response to standard format"""
        formatted_response = []

        if is_error or data is None:
            formatted_response.append(
                {
                    "source": "Account Exist(Mobile No)",
                    "type": "telegram",
                    "value": "No",
                    "showSource": True,
                    "category": "TEXT",
                }
            )
        else:
            for key, value in data.items():
                if key == "profile_photo":
                    # Skip profile photo for now (S3 removed)
                    continue
                else:
                    formatted_response.append(
                        {
                            "source": key,
                            "type": "telegram",
                            "value": self._check_for_tg_values(value),
                            "showSource": True,
                            "category": "TEXT",
                        }
                    )

        return formatted_response

    async def search_phone(self, country_code: str, phone: str) -> dict[str, Any]:
        """Search phone number using Telegram API"""
        client = None
        try:
            logger.info(f"Telegram: Searching {country_code}{phone}")

            # Get random account configuration
            account_config = self._get_random_account_config()
            if not account_config:
                raise ValueError("No Telegram account configured")

            api_id, api_hash, auth_mobile = account_config

            # Construct full phone number
            phone_to_search = country_code + phone

            # Login to Telegram
            client = await self._login(api_id, api_hash, auth_mobile)

            # Get user data
            user_data = await self._get_user_data(client, phone_to_search)

            # Format response
            is_error = user_data is None
            formatted_data = self._format_response(user_data, is_error=is_error)

            found = user_data is not None

            raw_response = {"user_data": user_data, "phone": phone_to_search}

            return {
                "found": found,
                "source": "telegram",
                "data": formatted_data,
                "confidence": 0.9 if found else 0.0,
                "_raw_response": raw_response,
            }

        except Exception as e:
            logger.error(f"Telegram search failed: {e}")
            raw_response = {"error": str(e), "exception_type": type(e).__name__}
            formatted_data = self._format_response(None, is_error=True)
            return {
                "found": False,
                "source": "telegram",
                "data": formatted_data,
                "error": str(e),
                "_raw_response": raw_response,
            }
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting Telegram client: {e}")
