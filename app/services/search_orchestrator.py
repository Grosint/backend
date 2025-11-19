import logging
from collections.abc import Awaitable, Callable
from typing import Any

from bson import ObjectId

from app.adapters.domain_adapter import DomainAdapter
from app.adapters.email_adapter import EmailAdapter
from app.adapters.phone_lookup_adapter import PhoneLookupAdapter
from app.models.result import ResultCreate
from app.models.search import SearchStatus, SearchType, SearchUpdate
from app.services.generic_orchestrator import GenericOrchestrator
from app.services.result_service import ResultService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Orchestrates multiple OSINT adapters and manages search operations"""

    def __init__(self, db):
        self.db = db
        self.search_service = SearchService(db)
        self.result_service = ResultService(db)
        self.orchestrator = GenericOrchestrator()

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
        Execute a search using multiple adapters

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

            # Build orchestrator tasks using adapters' normalized outputs
            # Use switch-style mapping instead of if-else chain
            task_defs: list[tuple[str, Callable[[], Awaitable[dict[str, Any]]]]] = []
            get_search_method = self.search_method_map.get(search.search_type)

            if not get_search_method:
                raise ValueError(
                    f"No search method available for search type: {search.search_type}"
                )

            for adapter in adapters:
                fn = get_search_method(adapter, search.query)
                task_defs.append((adapter.name, fn))

            orchestration = await self.orchestrator.execute(
                user_id=None,
                query_type=str(search.search_type),
                query_input={"query": search.query},
                tasks=task_defs,
            )

            # Summarize results stored via history for API response continuity
            # Maintain result_service persistence for backward compatibility
            successful_results = 0
            failed_results = 0
            for adapter in adapters:
                try:
                    # Persist minimal result record for legacy callers if needed
                    result = {"adapter": adapter.name}
                    result_create = ResultCreate(
                        search_id=ObjectId(search_id),
                        source=adapter.name,
                        data=result,
                        confidence_score=1.0,
                    )
                    await self.result_service.create_result(result_create)
                    successful_results += 1
                except Exception as e:
                    logger.error(f"Result persistence failed for {adapter.name}: {e}")
                    failed_results += 1

            status = (
                SearchStatus.COMPLETED
                if successful_results > 0
                else SearchStatus.FAILED
            )
            error_message = (
                None if failed_results == 0 else f"{failed_results} adapters failed"
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
                "status": status,
                "results_count": successful_results,
                "failed_count": failed_results,
                "error_message": error_message,
                "results": [self._format_result(r) for r in search_results],
                "history": orchestration,
            }

        except Exception as e:
            logger.error(f"Error executing search {search_id}: {e}")

            # Update search status to failed
            await self.search_service.update_search(
                search_id,
                SearchUpdate(status=SearchStatus.FAILED, error_message=str(e)),
            )

            raise

    async def _execute_email_search(
        self, adapter, query: str, search_id: str
    ) -> dict[str, Any]:
        """Execute email search using adapter"""
        try:
            # Execute the search
            result = await adapter.search_email(query)

            # Save result to database
            result_create = ResultCreate(
                search_id=ObjectId(search_id),
                source=adapter.name,
                data=result,
                confidence_score=result.get("summary", {}).get("successful_sources", 0)
                / result.get("summary", {}).get("total_sources", 1),
            )

            await self.result_service.create_result(result_create)

            return result

        except Exception as e:
            logger.error(f"Error in email search with {adapter.name}: {e}")
            raise

    async def _execute_domain_search(
        self, adapter, query: str, search_id: str
    ) -> dict[str, Any]:
        """Execute domain search using adapter"""
        try:
            # Execute the search
            result = await adapter.search_domain(query)

            # Save result to database
            result_create = ResultCreate(
                search_id=ObjectId(search_id),
                source=adapter.name,
                data=result,
                confidence_score=result.get("summary", {}).get("successful_sources", 0)
                / result.get("summary", {}).get("total_sources", 1),
            )

            await self.result_service.create_result(result_create)

            return result

        except Exception as e:
            logger.error(f"Error in domain search with {adapter.name}: {e}")
            raise

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

    def _get_email_search_method(self, adapter, query: str):
        """Get email search method for adapter"""

        async def fn(a=adapter, q=query):
            raw = await a.search_email(q)
            return raw

        return fn

    def _get_domain_search_method(self, adapter, query: str):
        """Get domain search method for adapter"""

        async def fn(a=adapter, q=query):
            raw = await a.search_domain(q)
            return raw

        return fn

    def _get_phone_search_method(self, adapter, query: str):
        """Get phone search method for adapter"""

        async def fn(a=adapter, q=query):
            # Parse country code and phone from query
            # Query format can be:
            # 1. "country_code:phone" (with colon separator)
            # 2. "+country_code+phone" (concatenated, e.g., "+919997260627")
            # 3. Just "phone" (default to +1)
            if ":" in q:
                # Format: "country_code:phone"
                parts = q.split(":", 1)
                country_code, phone = parts
            elif q.startswith("+"):
                # Format: "+country_code+phone" - extract country code
                # Country codes are typically 1-3 digits after the +
                remaining = q[1:]  # Remove the leading +

                # Common country code patterns (1-3 digits)
                # Try to intelligently split: country codes are usually 1-3 digits
                # Phone numbers are typically 7-15 digits total
                # Strategy: Try 1, 2, then 3 digit country codes
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
                    # Try 1-digit country code first
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
                phone = q

            raw = await a.search_phone(country_code, phone)
            return raw

        return fn

    def _get_username_search_method(self, adapter, query: str):
        """Get username search method for adapter"""

        async def fn(a=adapter, q=query):
            # Placeholder for username search
            raise NotImplementedError("Username search not yet implemented")

        return fn
