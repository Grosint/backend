from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from app.models.result import Result, ResultCreate, ResultUpdate

logger = logging.getLogger(__name__)


class ResultService:
    """Service for managing search results"""

    def __init__(self, db):
        self.db = db

    async def create_result(self, result_create: ResultCreate) -> Result:
        """Create a new result"""
        try:
            result = Result(
                search_id=result_create.search_id,
                source=result_create.source,
                data=result_create.data,
                confidence_score=result_create.confidence_score,
            )
            await result.insert()
            logger.info(
                f"Result created for search {result_create.search_id} from {result_create.source}"
            )
            return result
        except Exception as e:
            logger.error(f"Error creating result: {e}")
            raise

    async def get_result_by_id(self, result_id: str) -> Result | None:
        """Get a result by ID"""
        try:
            return await Result.get(ObjectId(result_id))
        except Exception as e:
            logger.error(f"Error getting result {result_id}: {e}")
            return None

    async def get_results_by_search_id(self, search_id: str) -> list[Result]:
        """Get all results for a search"""
        try:
            return await Result.find(Result.search_id == ObjectId(search_id)).to_list()
        except Exception as e:
            logger.error(f"Error getting results for search {search_id}: {e}")
            return []

    async def update_result(
        self, result_id: str, result_update: ResultUpdate
    ) -> Result | None:
        """Update a result"""
        try:
            result = await Result.get(ObjectId(result_id))
            if not result:
                return None

            if result_update.data is not None:
                result.data = result_update.data
            if result_update.confidence_score is not None:
                result.confidence_score = result_update.confidence_score

            await result.save()
            logger.info(f"Result {result_id} updated")
            return result
        except Exception as e:
            logger.error(f"Error updating result {result_id}: {e}")
            return None

    async def delete_result(self, result_id: str) -> bool:
        """Delete a result"""
        try:
            result = await Result.get(ObjectId(result_id))
            if result:
                await result.delete()
                logger.info(f"Result {result_id} deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting result {result_id}: {e}")
            return False

    async def get_result_stats(self, search_id: str) -> dict[str, Any]:
        """Get statistics for results of a search"""
        try:
            results = await self.get_results_by_search_id(search_id)

            stats = {
                "total": len(results),
                "by_source": {},
                "avg_confidence": 0.0,
                "sources": set(),
            }

            if not results:
                return stats

            total_confidence = 0.0
            for result in results:
                # Count by source
                source = result.source
                if source not in stats["by_source"]:
                    stats["by_source"][source] = 0
                stats["by_source"][source] += 1

                # Track sources
                stats["sources"].add(source)

                # Sum confidence for average
                total_confidence += result.confidence_score

            stats["avg_confidence"] = total_confidence / len(results)
            stats["sources"] = list(stats["sources"])

            return stats
        except Exception as e:
            logger.error(f"Error getting result stats for search {search_id}: {e}")
            return {"total": 0, "by_source": {}, "avg_confidence": 0.0, "sources": []}
