import asyncio
import logging
from typing import Any

from bson import ObjectId

from app.adapters.domain_adapter import DomainAdapter
from app.adapters.email_adapter import EmailAdapter
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

        # Adapter mapping
        self.adapters = {
            SearchType.EMAIL: [self.email_adapter],
            SearchType.DOMAIN: [self.domain_adapter],
            SearchType.PHONE: [],  # Add phone adapters here
            SearchType.USERNAME: [],  # Add username adapters here
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

            # Execute searches concurrently
            tasks = []
            for adapter in adapters:
                if search.search_type == SearchType.EMAIL:
                    task = self._execute_email_search(adapter, search.query, search_id)
                elif search.search_type == SearchType.DOMAIN:
                    task = self._execute_domain_search(adapter, search.query, search_id)
                else:
                    continue

                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            successful_results = 0
            failed_results = 0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Adapter {i} failed: {result}")
                    failed_results += 1
                else:
                    successful_results += 1

            # Update search status
            if failed_results == len(tasks):
                status = SearchStatus.FAILED
                error_message = "All adapters failed"
            elif failed_results > 0:
                status = SearchStatus.COMPLETED
                error_message = f"{failed_results} adapters failed"
            else:
                status = SearchStatus.COMPLETED
                error_message = None

            # Update search with final status
            await self.search_service.update_search(
                search_id,
                SearchUpdate(
                    status=status,
                    results_count=successful_results,
                    error_message=error_message,
                ),
            )

            # Get all results for this search
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
                    "type": search.search_type,
                    "query": search.query,
                    "status": search.status,
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
