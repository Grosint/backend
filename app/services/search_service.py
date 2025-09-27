from __future__ import annotations

import logging
from datetime import datetime

from bson import ObjectId

from app.core.config import settings
from app.models.search import SearchCreate, SearchInDB, SearchStatus, SearchUpdate

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, db):
        self.db = db
        self.collection = db[settings.MONGODB_COLLECTION_SEARCHES]

    async def create_search(self, search: SearchCreate) -> SearchInDB:
        """Create a new search"""
        try:
            search_doc = {
                "search_type": search.search_type,
                "query": search.query,
                "user_id": search.user_id,
                "status": SearchStatus.PENDING,
                "results_count": 0,
                "error_message": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            result = await self.collection.insert_one(search_doc)
            search_doc["_id"] = result.inserted_id

            logger.info(f"Search created: {search.search_type} - {search.query}")
            return SearchInDB(**search_doc)

        except Exception as e:
            logger.error(f"Error creating search: {e}")
            raise

    async def get_search_by_id(self, search_id: str) -> SearchInDB | None:
        """Get search by ID"""
        try:
            search_doc = await self.collection.find_one({"_id": ObjectId(search_id)})
            if search_doc:
                return SearchInDB(**search_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting search by ID: {e}")
            raise

    async def update_search(
        self, search_id: str, search_update: SearchUpdate
    ) -> SearchInDB | None:
        """Update search"""
        try:
            update_data = search_update.dict(exclude_unset=True)
            if not update_data:
                return await self.get_search_by_id(search_id)

            update_data["updated_at"] = datetime.utcnow()

            result = await self.collection.update_one(
                {"_id": ObjectId(search_id)}, {"$set": update_data}
            )

            if result.modified_count:
                return await self.get_search_by_id(search_id)
            return None
        except Exception as e:
            logger.error(f"Error updating search: {e}")
            raise

    async def list_searches_by_user(
        self, user_id: str, skip: int = 0, limit: int = 100
    ) -> list[SearchInDB]:
        """List searches by user with pagination"""
        try:
            cursor = (
                self.collection.find({"user_id": ObjectId(user_id)})
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            searches = []
            async for search_doc in cursor:
                searches.append(SearchInDB(**search_doc))
            return searches
        except Exception as e:
            logger.error(f"Error listing searches by user: {e}")
            raise

    async def list_searches(self, skip: int = 0, limit: int = 100) -> list[SearchInDB]:
        """List all searches with pagination"""
        try:
            cursor = (
                self.collection.find().sort("created_at", -1).skip(skip).limit(limit)
            )
            searches = []
            async for search_doc in cursor:
                searches.append(SearchInDB(**search_doc))
            return searches
        except Exception as e:
            logger.error(f"Error listing searches: {e}")
            raise

    async def delete_search(self, search_id: str) -> bool:
        """Delete search"""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(search_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting search: {e}")
            raise

    async def get_search_stats(self, user_id: str | None = None) -> dict:
        """Get search statistics"""
        try:
            match_filter = {"user_id": ObjectId(user_id)} if user_id else {}

            pipeline = [
                {"$match": match_filter},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            ]

            cursor = self.collection.aggregate(pipeline)
            stats = {}
            async for doc in cursor:
                stats[doc["_id"]] = doc["count"]

            return stats
        except Exception as e:
            logger.error(f"Error getting search stats: {e}")
            raise
