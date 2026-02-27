import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs

from beanie import PydanticObjectId
from bson import ObjectId

from app.adapters.bank_lookup_adapter import BankLookupAdapter
from app.adapters.dark_web_leak_adapter import DarkWebLeakAdapter
from app.adapters.domain_adapter import DomainAdapter
from app.adapters.email_adapter import EmailAdapter
from app.adapters.imei_lookup_adapter import IMEILookupAdapter
from app.adapters.ip_lookup_adapter import IPLookupAdapter
from app.adapters.phone_lookup_adapter import PhoneLookupAdapter
from app.adapters.vehicle_lookup_adapter import VehicleLookupAdapter
from app.adapters.verify_id_adapter import VerifyIdAdapter
from app.adapters.virtual_email_adapter import VirtualEmailAdapter
from app.adapters.virtual_number_adapter import VirtualNumberAdapter
from app.core.response_utils import normalize_source_or_type
from app.models.history import HistorySourceResult
from app.models.result import ResultCreate
from app.models.search import SearchStatus, SearchType, SearchUpdate
from app.services.history_service import HistoryService
from app.services.result_service import ResultService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Orchestrates multiple OSINT adapters and manages search operations"""

    def __init__(self, db):
        self.db = db
        self.search_service = SearchService(db)
        self.result_service = ResultService(db)
        self.history_service = HistoryService()

        # Initialize adapters
        self.email_adapter = EmailAdapter()
        self.domain_adapter = DomainAdapter()
        self.phone_lookup_adapter = PhoneLookupAdapter()
        self.vehicle_lookup_adapter = VehicleLookupAdapter()
        self.bank_lookup_adapter = BankLookupAdapter()
        self.verify_id_adapter = VerifyIdAdapter()
        self.ip_lookup_adapter = IPLookupAdapter()
        self.imei_lookup_adapter = IMEILookupAdapter()
        self.virtual_number_adapter = VirtualNumberAdapter()
        self.virtual_email_adapter = VirtualEmailAdapter()
        self.dark_web_leak_adapter = DarkWebLeakAdapter()

        # Adapter mapping
        self.adapters = {
            SearchType.EMAIL: [self.email_adapter],
            SearchType.DOMAIN: [self.domain_adapter],
            SearchType.PHONE: [self.phone_lookup_adapter],
            SearchType.VEHICLE_RC: [self.vehicle_lookup_adapter],
            SearchType.VEHICLE_FAST_TAG: [self.vehicle_lookup_adapter],
            SearchType.VEHICLE_ALL: [self.vehicle_lookup_adapter],
            SearchType.VEHICLE_CHASIS: [self.vehicle_lookup_adapter],
            SearchType.USERNAME: [],  # Add username adapters here
            SearchType.IP_LOOKUP: [self.ip_lookup_adapter],
            SearchType.IMEI_LOOKUP: [self.imei_lookup_adapter],
            SearchType.VIRTUAL_NUMBER: [self.virtual_number_adapter],
            SearchType.VIRTUAL_EMAIL: [self.virtual_email_adapter],
            SearchType.BANK_ACCOUNT: [self.bank_lookup_adapter],
            SearchType.VERIFY_ID: [self.verify_id_adapter],
            SearchType.DARK_WEB_LEAK: [self.dark_web_leak_adapter],
        }

        # Map search type to adapter method
        self.search_method_map = {
            SearchType.EMAIL: self._get_email_search_method,
            SearchType.DOMAIN: self._get_domain_search_method,
            SearchType.PHONE: self._get_phone_search_method,
            SearchType.VEHICLE_RC: self._get_vehicle_search_method,
            SearchType.VEHICLE_FAST_TAG: self._get_vehicle_search_method,
            SearchType.VEHICLE_ALL: self._get_vehicle_search_method,
            SearchType.VEHICLE_CHASIS: self._get_vehicle_search_method,
            SearchType.USERNAME: self._get_username_search_method,
            SearchType.IP_LOOKUP: self._get_ip_search_method,
            SearchType.IMEI_LOOKUP: self._get_imei_search_method,
            SearchType.VIRTUAL_NUMBER: self._get_virtual_number_search_method,
            SearchType.VIRTUAL_EMAIL: self._get_virtual_email_search_method,
            SearchType.BANK_ACCOUNT: self._get_bank_search_method,
            SearchType.VERIFY_ID: self._get_verify_id_search_method,
            SearchType.DARK_WEB_LEAK: self._get_dark_web_leak_search_method,
        }

    async def execute_search(self, search_id: str) -> dict[str, Any]:
        """
        Execute a search using the appropriate adapter/orchestrator

        Args:
            search_id: ID of the search to execute

        Returns:
            dict: Search results and status
        """
        history = None  # Initialize before try block to avoid UnboundLocalError
        try:
            # Get search details
            search = await self.search_service.get_search_by_id(search_id)
            if not search:
                raise ValueError(f"Search {search_id} not found")

            # Update search status to in progress
            await self.search_service.update_search(
                search_id, SearchUpdate(status=SearchStatus.IN_PROGRESS)
            )

            logger.info(
                f"Starting search execution for {search.search_type}: {search.query}"
            )

            # Create history record for this search
            if search.user_id:
                try:
                    # Map search type to history query type
                    query_type_map = {
                        SearchType.PHONE: "phone-lookup",
                        SearchType.EMAIL: "email-lookup",
                        SearchType.DOMAIN: "domain-lookup",
                        SearchType.VEHICLE_RC: "vehicle-rc",
                        SearchType.VEHICLE_FAST_TAG: "vehicle-fast-tag",
                        SearchType.VEHICLE_ALL: "vehicle-all",
                        SearchType.VEHICLE_CHASIS: "vehicle-chasis",
                        SearchType.USERNAME: "username-lookup",
                        SearchType.IP_LOOKUP: "ip-lookup",
                        SearchType.IMEI_LOOKUP: "imei-lookup",
                        SearchType.VIRTUAL_NUMBER: "virtual-number",
                        SearchType.VIRTUAL_EMAIL: "virtual-email",
                        SearchType.BANK_ACCOUNT: "bank-account",
                        SearchType.VERIFY_ID: "verify-id",
                        SearchType.DARK_WEB_LEAK: "dark-web-leak",
                    }
                    query_type = query_type_map.get(search.search_type, "search")

                    history = await self.history_service.create_history(
                        user_id=PydanticObjectId(str(search.user_id)),
                        query_type=query_type,
                        query_input=search.query,
                    )
                    logger.info(
                        f"History created for search: {search.id} -> history: {history.id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to create history for search {search.id}: {e}"
                    )

            # Get adapters for this search type
            adapters = self.adapters.get(search.search_type, [])
            if not adapters:
                raise ValueError(
                    f"No adapters available for search type: {search.search_type}"
                )

            # Build search tasks using adapters' normalized outputs
            # Use switch-style mapping instead of if-else chain
            get_search_method = self.search_method_map.get(search.search_type)
            if not get_search_method:
                raise ValueError(
                    f"No search method available for search type: {search.search_type}"
                )

            # Execute all adapters in parallel
            tasks = []
            for adapter in adapters:
                search_fn = get_search_method(adapter, search.query)
                tasks.append(
                    self._execute_adapter_search(adapter, search_fn, search_id)
                )

            # Execute all adapter searches in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and store in database
            successful_results = 0
            failed_results = 0
            all_results_data = []

            for i, result in enumerate(results):
                adapter = adapters[i]
                if isinstance(result, Exception):
                    logger.error(f"Search failed for adapter {adapter.name}: {result}")
                    failed_results += 1
                    # Add failed result to history if history exists
                    if history:
                        try:
                            history_result = HistorySourceResult(
                                source=adapter.name,
                                success=False,
                                errorCode="EXCEPTION",
                                message=str(result),
                            )
                            await self.history_service.add_result(
                                history.id, history_result
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to add history result for {adapter.name}: {e}"
                            )
                else:
                    # Store results from the adapter/orchestrator
                    result_data = await self._store_adapter_results(
                        search_id, adapter, result, history
                    )
                    successful_results += result_data["successful_count"]
                    failed_results += result_data["failed_count"]
                    all_results_data.append(result_data)

            status = (
                SearchStatus.COMPLETED
                if successful_results > 0
                else SearchStatus.FAILED
            )
            error_message = (
                None if failed_results == 0 else f"{failed_results} sources failed"
            )

            await self.search_service.update_search(
                search_id,
                SearchUpdate(
                    status=status,
                    results_count=successful_results,
                    error_message=error_message,
                ),
            )

            search_results = await self.result_service.get_results_by_search_id(
                search_id
            )

            logger.info(f"Search execution completed: {search_id} - Status: {status}")

            # Flatten all results into a single list
            flattened_results = []
            for result in search_results:
                flattened_data = self._flatten_result_data(result.data, result.source)
                flattened_results.extend(flattened_data)

            # Store flattened results in history if history was created
            if history:
                try:
                    total_sources = successful_results + failed_results
                    await self.history_service.finalize_history(
                        history.id,
                        total_sources=total_sources,
                        flattened_results=flattened_results,
                    )
                    logger.info(
                        f"History finalized with {len(flattened_results)} flattened results: {history.id}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to finalize history {history.id}: {e}")

            return {
                "search_id": search_id,
                "status": status.value,
                "results_count": successful_results,
                "failed_count": failed_results,
                "error_message": error_message,
                "results": flattened_results,
                "history_id": str(history.id) if history else None,
            }

        except Exception as e:
            logger.error(f"Error executing search {search_id}: {e}")

            # Update search status to failed
            await self.search_service.update_search(
                search_id,
                SearchUpdate(status=SearchStatus.FAILED, error_message=str(e)),
            )

            # Finalize history with failed status if history was created
            if history:
                try:
                    await self.history_service.finalize_history(
                        history.id,
                        total_sources=0,
                        flattened_results=[],
                    )
                    logger.info(f"History finalized with failed status: {history.id}")
                except Exception as history_error:
                    logger.warning(
                        f"Failed to finalize history {history.id}: {history_error}"
                    )

            raise

    async def _execute_adapter_search(
        self,
        adapter: Any,
        search_fn: Callable[[], Awaitable[dict[str, Any]]],
        search_id: str,
    ) -> dict[str, Any]:
        """Execute search using adapter's search function"""
        try:
            result = await search_fn()
            return result
        except Exception as e:
            logger.error(f"Error executing search with {adapter.name}: {e}")
            raise

    async def _store_adapter_results(
        self, search_id: str, adapter: Any, result: dict[str, Any], history: Any = None
    ) -> dict[str, Any]:
        """Store adapter results in database and return counts"""
        successful_count = 0
        failed_count = 0

        if not result.get("success", False):
            # Add failed result to history if history exists
            if history:
                try:
                    history_result = HistorySourceResult(
                        source=adapter.name,
                        success=False,
                        errorCode="ADAPTER_FAILED",
                        message=result.get("error", "Adapter returned success=False"),
                        data=result,
                    )
                    await self.history_service.add_result(history.id, history_result)
                except Exception as e:
                    logger.warning(
                        f"Failed to add history result for {adapter.name}: {e}"
                    )
            return {"successful_count": 0, "failed_count": 1}

        data = result.get("data", {})
        normalized_data = normalize_source_or_type(data)
        lookup_results = normalized_data.get("lookup_results", {})

        logger.debug(
            "Storing adapter lookup results: adapter=%s, lookup_results_keys=%s, has_lookup_results=%s",
            getattr(adapter, "name", None),
            list(lookup_results.keys()) if isinstance(lookup_results, dict) else [],
            bool(lookup_results),
        )

        # For phone and email, store each source result separately
        if lookup_results:
            for source_name, source_result in lookup_results.items():
                try:
                    is_success = False
                    if isinstance(source_result, dict) and "error" not in source_result:
                        if source_result.get("found", False):
                            successful_count += 1
                            is_success = True
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1

                    result_create = ResultCreate(
                        search_id=ObjectId(search_id),
                        source=source_name,
                        data=normalize_source_or_type(source_result),
                        confidence_score=(
                            source_result.get("confidence", 0.0)
                            if isinstance(source_result, dict)
                            else 0.0
                        ),
                    )
                    await self.result_service.create_result(result_create)

                    logger.debug(
                        "Stored source result summary: source=%s, is_success=%s, has_error=%s, found=%s, has_data=%s",
                        source_name,
                        is_success,
                        isinstance(source_result, dict) and "error" in source_result,
                        (
                            source_result.get("found", False)
                            if isinstance(source_result, dict)
                            else False
                        ),
                        isinstance(source_result, dict)
                        and source_result.get("data") is not None,
                    )

                    # Add result to history if history exists
                    if history:
                        try:
                            history_result = HistorySourceResult(
                                source=source_name,
                                success=is_success,
                                data=(
                                    source_result
                                    if isinstance(source_result, dict)
                                    else None
                                ),
                                errorCode=(
                                    (
                                        None
                                        if is_success
                                        else source_result.get("error", "NOT_FOUND")
                                    )
                                    if isinstance(source_result, dict)
                                    else "INVALID_FORMAT"
                                ),
                                message=(
                                    (
                                        None
                                        if is_success
                                        else source_result.get(
                                            "message", "No data found"
                                        )
                                    )
                                    if isinstance(source_result, dict)
                                    else "Invalid result format"
                                ),
                            )
                            await self.history_service.add_result(
                                history.id, history_result
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to add history result for {source_name}: {e}"
                            )
                except Exception as e:
                    logger.error(f"Error storing result for {source_name}: {e}")
                    failed_count += 1
                    # Add failed result to history if history exists
                    if history:
                        try:
                            history_result = HistorySourceResult(
                                source=source_name,
                                success=False,
                                errorCode="STORAGE_ERROR",
                                message=str(e),
                            )
                            await self.history_service.add_result(
                                history.id, history_result
                            )
                        except Exception as history_err:
                            logger.warning(
                                f"Failed to add history result for {source_name}: {history_err}"
                            )
        else:
            # For domain and other adapters, store the main result
            try:
                confidence_score = data.get("summary", {}).get(
                    "successful_sources", 0
                ) / max(data.get("summary", {}).get("total_sources", 1), 1)
                result_create = ResultCreate(
                    search_id=ObjectId(search_id),
                    source=adapter.name,
                    data=data,
                    confidence_score=confidence_score,
                )
                await self.result_service.create_result(result_create)
                successful_count = data.get("summary", {}).get("successful_sources", 0)
                failed_count = (
                    data.get("summary", {}).get("total_sources", 0) - successful_count
                )

                # Add result to history if history exists
                if history:
                    try:
                        is_success = successful_count > 0
                        history_result = HistorySourceResult(
                            source=adapter.name,
                            success=is_success,
                            data=data,
                            errorCode=None if is_success else "NO_SUCCESSFUL_SOURCES",
                            message=(
                                None if is_success else "No successful sources found"
                            ),
                        )
                        await self.history_service.add_result(
                            history.id, history_result
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to add history result for {adapter.name}: {e}"
                        )
            except Exception as e:
                logger.error(f"Error storing result for {adapter.name}: {e}")
                failed_count += 1
                # Add failed result to history if history exists
                if history:
                    try:
                        history_result = HistorySourceResult(
                            source=adapter.name,
                            success=False,
                            errorCode="STORAGE_ERROR",
                            message=str(e),
                        )
                        await self.history_service.add_result(
                            history.id, history_result
                        )
                    except Exception as history_err:
                        logger.warning(
                            f"Failed to add history result for {adapter.name}: {history_err}"
                        )

        return {
            "successful_count": successful_count,
            "failed_count": failed_count,
        }

    def _get_email_search_method(
        self, adapter: EmailAdapter, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        """Get email search method for adapter"""

        async def fn(a=adapter, q=query):
            raw = await a.search_email(q)
            return raw

        return fn

    def _get_domain_search_method(
        self, adapter: DomainAdapter, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        """Get domain search method for adapter"""

        async def fn(a=adapter, q=query):
            raw = await a.search_domain(q)
            return raw

        return fn

    def _get_phone_search_method(
        self, adapter: PhoneLookupAdapter, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        """Get phone search method for adapter"""

        # Support optional "ADV|" prefix to signal advanced phone lookup
        is_advance = False
        normalized_query = query
        if query.startswith("ADV|"):
            is_advance = True
            normalized_query = query[4:]

        async def fn(a=adapter, q=normalized_query, adv=is_advance):
            # Parse country code and phone from query
            country_code, phone = self._parse_phone_query(q)
            raw = await a.search_phone(country_code, phone, is_advance=adv)
            return raw

        return fn

    def _get_vehicle_search_method(
        self, adapter: VehicleLookupAdapter, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        """Get vehicle search method for adapter"""

        vehicle_number, chassis_number, lookup_type = self._parse_vehicle_query(query)

        async def fn(a=adapter, v=vehicle_number, c=chassis_number, t=lookup_type):
            raw = await a.search_vehicle(v, chassis_number=c, lookup_type=t)
            return raw

        return fn

    def _get_username_search_method(
        self, adapter: Any, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        """Get username search method for adapter"""

        async def fn(a=adapter, q=query):
            # Placeholder for username search
            raise NotImplementedError("Username search not yet implemented")

        return fn

    def _get_ip_search_method(
        self, adapter: Any, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        async def fn(a=adapter, q=query):
            return await a.search_ip(q)

        return fn

    def _get_imei_search_method(
        self, adapter: Any, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        async def fn(a=adapter, q=query):
            return await a.search_imei(q)

        return fn

    def _get_virtual_number_search_method(
        self, adapter: Any, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        phone_number, country_code = self._parse_virtual_number_query(query)

        async def fn(a=adapter, ph=phone_number, cc=country_code):
            return await a.search_virtual_number(ph, cc)

        return fn

    def _parse_virtual_number_query(self, query: str) -> tuple[str, str]:
        """Parse virtual number query: ph=X|cc=Y or raw phone (default cc=+91)"""
        phone_number, country_code = query, "+91"
        for part in query.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "ph":
                    phone_number = v
                elif k == "cc":
                    country_code = v if v.startswith("+") else "+" + v
        return phone_number, country_code

    def _get_virtual_email_search_method(
        self, adapter: Any, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        async def fn(a=adapter, q=query):
            return await a.search_virtual_email(q)

        return fn

    def _get_bank_search_method(
        self, adapter: Any, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        account_no, ifsc_code, upi = self._parse_bank_query(query)

        async def fn(a=adapter, acc=account_no, ifsc=ifsc_code, u=upi):
            return await a.search_bank(account_no=acc, ifsc_code=ifsc, upi=u)

        return fn

    def _get_verify_id_search_method(
        self, adapter: Any, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        id_type, value, dob = self._parse_verify_id_query(query)

        async def fn(a=adapter, it=id_type, v=value, d=dob):
            return await a.search_verify_id(id_type=it, value=v, dob=d)

        return fn

    def _get_dark_web_leak_search_method(
        self, adapter: Any, query: str
    ) -> Callable[[], Awaitable[dict[str, Any]]]:
        query_type, query_data, country_code = self._parse_dark_web_leak_query(query)

        async def fn(a=adapter, qt=query_type, qd=query_data, cc=country_code):
            return await a.search_leak(query_type=qt, query_data=qd, country_code=cc)

        return fn

    def _parse_dark_web_leak_query(self, query: str) -> tuple[str, str, str]:
        """Parse dark web leak query: type=email|value=X or type=phone|value=X|cc=+91"""
        query_type, query_data, country_code = "email", "", "+91"
        for part in query.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "type":
                    query_type = v or "email"
                elif k == "value":
                    query_data = v
                elif k == "cc":
                    country_code = v if v.startswith("+") else "+" + v if v else "+91"
        return query_type, query_data, country_code

    def _parse_bank_query(
        self, query: str
    ) -> tuple[str | None, str | None, str | None]:
        """Parse bank query: acc=X|ifsc=Y or upi=Z"""
        account_no, ifsc_code, upi = None, None, None
        for part in query.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "acc":
                    account_no = v or None
                elif k == "ifsc":
                    ifsc_code = v or None
                elif k == "upi":
                    upi = v or None
        return account_no, ifsc_code, upi

    def _parse_verify_id_query(self, query: str) -> tuple[str, str, str | None]:
        """Parse verify ID query: type=pan|value=X or type=dl|value=X|dob=DD-MM-YYYY"""
        id_type, value, dob = "pan", "", None
        for part in query.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "type":
                    id_type = v or "pan"
                elif k == "value":
                    value = v
                elif k == "dob":
                    dob = v or None
        return id_type, value, dob

    def _parse_phone_query(self, query: str) -> tuple[str, str]:
        """Parse phone query into country_code and phone"""
        # Query format can be:
        # 1. "country_code:phone" (with colon separator)
        # 2. "+country_code+phone" (concatenated, e.g., "+919997260627")
        # 3. Just "phone" (default to +1)
        if ":" in query:
            # Format: "country_code:phone"
            parts = query.split(":", 1)
            country_code, phone = parts
        elif query.startswith("+"):
            # Format: "+country_code+phone" - extract country code
            remaining = query[1:]  # Remove the leading +

            # Common country code patterns (1-3 digits)
            if len(remaining) > 10:
                # Likely has country code + phone
                # Try 2-digit first (most common: +91, +44, +86, etc.)
                if len(remaining) >= 11:
                    country_code = "+" + remaining[0:2]
                    phone = remaining[2:]
                # Try 1-digit (e.g., +1 for US/Canada)
                elif len(remaining) > 10:
                    country_code = "+" + remaining[0]
                    phone = remaining[1:]
                else:
                    country_code = "+1"
                    phone = remaining
            elif len(remaining) >= 7:
                # Might be just phone, or short country code
                if len(remaining) > 10:
                    country_code = "+" + remaining[0]
                    phone = remaining[1:]
                else:
                    # Assume it's phone only with + prefix
                    country_code = "+1"
                    phone = remaining
            else:
                # Too short, treat as phone only
                country_code = "+1"
                phone = remaining
        else:
            # No + prefix, treat as phone only
            country_code = "+1"  # Default to US
            phone = query

        return country_code, phone

    def _parse_vehicle_query(self, query: str) -> tuple[str | None, str | None, str]:
        """Parse vehicle query into vehicle_number, chassis_number, lookup_type.

        Supports URL-encoded format (veh=...&ch=...&type=...) and legacy
        pipe-delimited format for backward compatibility.
        """
        vehicle_number = query
        chassis_number = None
        lookup_type = "all"

        # URL-encoded format (e.g. veh=ABC&ch=XYZ&type=rc)
        if "&" in query and "veh=" in query:
            parsed = parse_qs(query)

            def _first(key: str, default: str | None = None) -> str | None:
                vals = parsed.get(key)
                if vals and vals[0]:
                    v = vals[0].strip()
                    return v or None
                return default

            vehicle_number = _first("veh")
            chassis_number = _first("ch")
            lookup_type = _first("type") or "all"
        elif "veh=" in query or "type=" in query:
            # Legacy pipe-delimited format
            parts = [p for p in query.split("|") if p]
            for part in parts:
                if part.startswith("veh="):
                    value = part.split("=", 1)[1]
                    vehicle_number = value or None
                elif part.startswith("ch="):
                    value = part.split("=", 1)[1]
                    chassis_number = value or None
                elif part.startswith("type="):
                    value = part.split("=", 1)[1]
                    lookup_type = value or "all"
        elif "|" in query:
            vehicle_number, chassis_number = query.split("|", 1)
            chassis_number = chassis_number or None

        return vehicle_number, chassis_number, lookup_type

    def _remove_raw_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively remove _raw_response from data dictionary"""
        if not isinstance(data, dict):
            return data

        cleaned = {}
        for key, value in data.items():
            if key == "_raw_response":
                # Skip _raw_response field
                continue
            elif isinstance(value, dict):
                cleaned[key] = self._remove_raw_response(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    self._remove_raw_response(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        return cleaned

    def _flatten_result_data(
        self, result_data: dict[str, Any], source: str
    ) -> list[dict[str, Any]]:
        """
        Flatten result data into a single list of items.

        For phone/email lookups, extracts data from nested structure:
        - If data.data exists and is a list, extract those items
        - Ensure each item has a 'source' field
        - Remove _raw_response from all nested structures

        Returns empty list if result has error or found=False
        """
        # Skip results with errors
        if not isinstance(result_data, dict):
            return []

        if "error" in result_data:
            logger.debug(
                "Flatten skipped due to error in result_data: source=%s",
                source,
            )
            return []

        # Remove _raw_response first
        cleaned_data = self._remove_raw_response(result_data)

        # If this is a phone/email lookup result with nested data structure
        normalized_cleaned = normalize_source_or_type(cleaned_data)

        if isinstance(normalized_cleaned, dict) and "data" in normalized_cleaned:
            inner_data = normalized_cleaned.get("data")

            # If inner data is a list, extract those items
            if isinstance(inner_data, list):
                flattened = []
                for item in inner_data:
                    if isinstance(item, dict):
                        # Create a copy to avoid mutating original
                        item_copy = item.copy()
                        # Ensure source is present
                        if "source" not in item_copy:
                            item_copy["source"] = source
                        flattened.append(item_copy)
                    else:
                        # If item is not a dict, wrap it
                        flattened.append(
                            {
                                "source": source,
                                "type": "unknown",
                                "value": str(item),
                                "category": "TEXT",
                            }
                        )
                return flattened
            elif isinstance(inner_data, dict):
                # If inner data is a dict, convert to list item
                item_copy = inner_data.copy()
                if "source" not in item_copy:
                    item_copy["source"] = source
                return [item_copy]

        # If data doesn't have nested structure, return as single item
        if isinstance(normalized_cleaned, dict):
            item_copy = normalized_cleaned.copy()
            if "source" not in item_copy:
                item_copy["source"] = source
            return [item_copy]

        # Fallback: wrap in a list
        return [
            {
                "source": source,
                "type": "unknown",
                "value": str(normalized_cleaned),
                "category": "TEXT",
            }
        ]

    def _format_result(self, result) -> dict[str, Any]:
        """Format result for API response - returns flattened data without _raw_response"""
        # Flatten the result data
        flattened_data = self._flatten_result_data(result.data, result.source)

        return {
            "id": str(result.id),
            "source": result.source,
            "data": flattened_data,
            "confidence_score": result.confidence_score,
            "created_at": result.created_at.isoformat(),
        }

    async def get_search_summary(self, search_id: str) -> dict[str, Any]:
        """Get summary of search results"""
        try:
            search = await self.search_service.get_search_by_id(search_id)
            if not search:
                raise ValueError(f"Search {search_id} not found")

            results = await self.result_service.get_results_by_search_id(search_id)
            stats = await self.result_service.get_result_stats(search_id)

            # Flatten all results into a single list
            flattened_results = []
            for result in results:
                flattened_data = self._flatten_result_data(result.data, result.source)
                flattened_results.extend(flattened_data)

            return {
                "search": {
                    "id": str(search.id),
                    "type": search.search_type.value,
                    "query": search.query,
                    "status": search.status.value,
                    "created_at": search.created_at.isoformat(),
                    "updated_at": search.updated_at.isoformat(),
                },
                "results": {
                    "total": len(results),
                    "by_source": stats,
                    "data": flattened_results,
                },
            }

        except Exception as e:
            logger.error(f"Error getting search summary: {e}")
            raise
