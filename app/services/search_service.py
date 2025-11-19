from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from app.models.search import (
    Search,
    SearchCreate,
    SearchStatus,
    SearchType,
    SearchUpdate,
)
from app.utils.validators import PyObjectId

logger = logging.getLogger(__name__)


class SearchService:
    """Service for managing searches"""

    def __init__(self, db):
        self.db = db

    async def create_search(self, search_create: SearchCreate) -> Search:
        """Create a new search"""
        try:
            search = Search(
                user_id=search_create.user_id,
                search_type=search_create.search_type,
                query=search_create.query,
                status=search_create.status,
            )
            await search.insert()
            logger.info(
                f"Search created: {search.id} - {search_create.search_type} for {search_create.query}"
            )
            return search
        except Exception as e:
            logger.error(
                f"Error creating search: {e}",
                extra={
                    "exception_type": type(e).__name__,
                    "search_type": (
                        search_create.search_type.value
                        if search_create.search_type
                        else None
                    ),
                    "query": search_create.query,
                    "user_id": (
                        str(search_create.user_id) if search_create.user_id else None
                    ),
                },
                exc_info=True,
            )
            raise

    async def get_search_by_id(self, search_id: str) -> Search | None:
        """Get a search by ID"""
        try:
            return await Search.get(ObjectId(search_id))
        except Exception as e:
            logger.error(f"Error getting search {search_id}: {e}")
            return None

    async def get_searches_by_user_id(
        self, user_id: str, limit: int = 20, skip: int = 0
    ) -> list[Search]:
        """Get searches for a user"""
        try:
            return (
                await Search.find(Search.user_id == PyObjectId(user_id))
                .sort("-created_at")
                .skip(skip)
                .limit(limit)
                .to_list()
            )
        except Exception as e:
            logger.error(f"Error getting searches for user {user_id}: {e}")
            return []

    async def get_searches_by_status(
        self, status: SearchStatus, limit: int = 20
    ) -> list[Search]:
        """Get searches by status"""
        try:
            return (
                await Search.find(Search.status == status)
                .sort("-created_at")
                .limit(limit)
                .to_list()
            )
        except Exception as e:
            logger.error(f"Error getting searches by status {status}: {e}")
            return []

    async def update_search(
        self, search_id: str, search_update: SearchUpdate
    ) -> Search | None:
        """Update a search"""
        try:
            search = await Search.get(ObjectId(search_id))
            if not search:
                return None

            if search_update.status is not None:
                search.status = search_update.status
            if search_update.results_count is not None:
                search.results_count = search_update.results_count
            if search_update.error_message is not None:
                search.error_message = search_update.error_message

            await search.save()
            logger.info(
                f"Search {search_id} updated: status={search.status}, results={search.results_count}"
            )
            return search
        except Exception as e:
            logger.error(f"Error updating search {search_id}: {e}")
            return None

    async def delete_search(self, search_id: str) -> bool:
        """Delete a search"""
        try:
            search = await Search.get(ObjectId(search_id))
            if search:
                await search.delete()
                logger.info(f"Search {search_id} deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting search {search_id}: {e}")
            return False

    async def get_search_stats(self) -> dict[str, Any]:
        """Get search statistics"""
        try:
            total_searches = await Search.count()

            # Count by status
            status_counts = {}
            for status in SearchStatus:
                count = await Search.find(Search.status == status).count()
                status_counts[status.value] = count

            # Count by type
            type_counts = {}
            for search_type in SearchType:
                count = await Search.find(Search.search_type == search_type).count()
                type_counts[search_type.value] = count

            return {
                "total_searches": total_searches,
                "by_status": status_counts,
                "by_type": type_counts,
            }
        except Exception as e:
            logger.error(f"Error getting search stats: {e}")
            return {
                "total_searches": 0,
                "by_status": {},
                "by_type": {},
            }
