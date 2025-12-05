import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from bson import ObjectId

from app.adapters.domain_adapter import DomainAdapter
from app.adapters.email_adapter import EmailAdapter
from app.adapters.phone_lookup_adapter import PhoneLookupAdapter
from app.models.result import ResultCreate
from app.models.search import SearchStatus, SearchType, SearchUpdate
from app.services.result_service import ResultService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Orchestrates multiple OSINT adapters and manages search operations"""

    def __init__(self, db):
        self.db = db
        self.search_service = SearchService(db)
        self.result_service = ResultService(db)

        # Initialize adapters
        self.email_adapter = EmailAdapter()
        self.domain_adapter = DomainAdapter()
        self.phone_lookup_adapter = PhoneLookupAdapter()

        # Adapter mapping
        self.adapters = {
            SearchType.EMAIL: [self.email_adapter],
            SearchType.DOMAIN: [self.domain_adapter],
            SearchType.PHONE: [self.phone_lookup_adapter],
            SearchType.USERNAME: [],  # Add username adapters here
        }

        # Map search type to adapter method
        self.search_method_map = {
            SearchType.EMAIL: self._get_email_search_method,
            SearchType.DOMAIN: self._get_domain_search_method,
            SearchType.PHONE: self._get_phone_search_method,
            SearchType.USERNAME: self._get_username_search_method,
        }

    async def execute_search(self, search_id: str) -> dict[str, Any]:
        """
        Execute a search using the appropriate adapter/orchestrator

        Args:
            search_id: ID of the search to execute

        Returns:
            dict: Search results and status
        """
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
                else:
                    # Store results from the adapter/orchestrator
                    result_data = await self._store_adapter_results(
                        search_id, adapter, result
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

            return {
                "search_id": search_id,
                "status": status.value,
                "results_count": successful_results,
                "failed_count": failed_results,
                "error_message": error_message,
                "results": [self._format_result(r) for r in search_results],
            }

        except Exception as e:
            logger.error(f"Error executing search {search_id}: {e}")

            # Update search status to failed
            await self.search_service.update_search(
                search_id,
                SearchUpdate(status=SearchStatus.FAILED, error_message=str(e)),
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
        self, search_id: str, adapter: Any, result: dict[str, Any]
    ) -> dict[str, Any]:
        """Store adapter results in database and return counts"""
        successful_count = 0
        failed_count = 0

        if not result.get("success", False):
            return {"successful_count": 0, "failed_count": 1}

        data = result.get("data", {})
        lookup_results = data.get("lookup_results", {})

        # For phone and email, store each source result separately
        if lookup_results:
            for source_name, source_result in lookup_results.items():
                try:
                    if isinstance(source_result, dict) and "error" not in source_result:
                        if source_result.get("found", False):
                            successful_count += 1
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1

                    result_create = ResultCreate(
                        search_id=ObjectId(search_id),
                        source=source_name,
                        data=source_result,
                        confidence_score=(
                            source_result.get("confidence", 0.0)
                            if isinstance(source_result, dict)
                            else 0.0
                        ),
                    )
                    await self.result_service.create_result(result_create)
                except Exception as e:
                    logger.error(f"Error storing result for {source_name}: {e}")
                    failed_count += 1
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
            except Exception as e:
                logger.error(f"Error storing result for {adapter.name}: {e}")
                failed_count += 1

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

        async def fn(a=adapter, q=query):
            # Parse country code and phone from query
            country_code, phone = self._parse_phone_query(q)
            raw = await a.search_phone(country_code, phone)
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

    def _format_result(self, result) -> dict[str, Any]:
        """Format result for API response"""
        return {
            "id": str(result.id),
            "source": result.source,
            "data": result.data,
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
                    "data": [self._format_result(r) for r in results],
                },
            }

        except Exception as e:
            logger.error(f"Error getting search summary: {e}")
            raise
