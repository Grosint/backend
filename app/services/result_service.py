from __future__ import annotations

import logging
from datetime import datetime

from bson import ObjectId

from app.core.config import settings
from app.models.result import ResultCreate, ResultInDB, ResultUpdate

logger = logging.getLogger(__name__)


class ResultService:
    def __init__(self, db):
        self.db = db
        self.collection = db[settings.MONGODB_COLLECTION_RESULTS]

    async def create_result(self, result: ResultCreate) -> ResultInDB:
        """Create a new result"""
        try:
            result_doc = {
                "search_id": result.search_id,
                "source": result.source,
                "data": result.data,
                "confidence_score": result.confidence_score,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            result_insert = await self.collection.insert_one(result_doc)
            result_doc["_id"] = result_insert.inserted_id

            logger.info(
                f"Result created for search {result.search_id} from source {result.source}"
            )
            return ResultInDB(**result_doc)

        except Exception as e:
            logger.error(f"Error creating result: {e}")
            raise

    async def get_result_by_id(self, result_id: str) -> ResultInDB | None:
        """Get result by ID"""
        try:
            result_doc = await self.collection.find_one({"_id": ObjectId(result_id)})
            if result_doc:
                return ResultInDB(**result_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting result by ID: {e}")
            raise

    async def get_results_by_search_id(self, search_id: str) -> list[ResultInDB]:
        """Get all results for a search"""
        try:
            cursor = self.collection.find({"search_id": ObjectId(search_id)}).sort(
                "created_at", -1
            )
            results = []
            async for result_doc in cursor:
                results.append(ResultInDB(**result_doc))
            return results
        except Exception as e:
            logger.error(f"Error getting results by search ID: {e}")
            raise

    async def update_result(
        self, result_id: str, result_update: ResultUpdate
    ) -> ResultInDB | None:
        """Update result"""
        try:
            update_data = result_update.dict(exclude_unset=True)
            if not update_data:
                return await self.get_result_by_id(result_id)

            update_data["updated_at"] = datetime.utcnow()

            result = await self.collection.update_one(
                {"_id": ObjectId(result_id)}, {"$set": update_data}
            )

            if result.modified_count:
                return await self.get_result_by_id(result_id)
            return None
        except Exception as e:
            logger.error(f"Error updating result: {e}")
            raise

    async def delete_result(self, result_id: str) -> bool:
        """Delete result"""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(result_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting result: {e}")
            raise

    async def delete_results_by_search_id(self, search_id: str) -> int:
        """Delete all results for a search"""
        try:
            result = await self.collection.delete_many(
                {"search_id": ObjectId(search_id)}
            )
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting results by search ID: {e}")
            raise

    async def get_results_by_source(
        self, source: str, skip: int = 0, limit: int = 100
    ) -> list[ResultInDB]:
        """Get results by source with pagination"""
        try:
            cursor = (
                self.collection.find({"source": source})
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            results = []
            async for result_doc in cursor:
                results.append(ResultInDB(**result_doc))
            return results
        except Exception as e:
            logger.error(f"Error getting results by source: {e}")
            raise

    async def get_result_stats(self, search_id: str | None = None) -> dict:
        """Get result statistics"""
        try:
            match_filter = {"search_id": ObjectId(search_id)} if search_id else {}

            pipeline = [
                {"$match": match_filter},
                {
                    "$group": {
                        "_id": "$source",
                        "count": {"$sum": 1},
                        "avg_confidence": {"$avg": "$confidence_score"},
                    }
                },
            ]

            cursor = self.collection.aggregate(pipeline)
            stats = {}
            async for doc in cursor:
                stats[doc["_id"]] = {
                    "count": doc["count"],
                    "avg_confidence": doc["avg_confidence"],
                }

            return stats
        except Exception as e:
            logger.error(f"Error getting result stats: {e}")
            raise
