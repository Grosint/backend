from __future__ import annotations

import logging
from typing import Any

import httpx
from ghunt.helpers.gmaps import get_reviews

from app.services.integrations.email_lookup.ghunt.credentials_manager import (
    GHuntCredentialsManager,
)

logger = logging.getLogger(__name__)


class GHuntMapsService:
    """Service for GHunt Google Maps integration"""

    def __init__(self):
        self.name = "GHuntMapsService"
        self._creds = None

    def _get_credentials(self):
        """Get GHunt credentials"""
        if self._creds is None:
            self._creds = GHuntCredentialsManager.get_credentials()
        return self._creds

    async def get_maps_reviews(self, gaia_id: str) -> dict[str, Any]:
        """Get Google Maps reviews for a GAIA ID"""
        try:
            async with httpx.AsyncClient() as client:
                # get_reviews returns: (error_status, stats, reviews, photos)
                error_status, stats, reviews, photos = await get_reviews(
                    client, gaia_id
                )

                if error_status == "failed":
                    return {"found": False, "error": "Failed to fetch reviews"}
                if error_status == "empty" or not reviews:
                    return {"found": False, "error": "No reviews found"}

                # Calculate photos stats from photos list
                photos_stats = {
                    "total_photos": len(photos),
                    "photos_with_location": sum(
                        1 for p in photos if hasattr(p, "location") and p.location
                    ),
                }

                return {
                    "found": True,
                    "total_reviews": len(reviews),
                    "reviews_stats": stats,
                    "photos_stats": photos_stats,
                    "reviews": self._process_reviews(reviews),
                    "photos": self._process_photos(photos),
                }
        except Exception as e:
            logger.error(f"GHunt Maps API error: {e}")
            return {"found": False, "error": str(e)}

    def _process_reviews(self, reviews: list) -> list[dict]:
        """Process raw review data"""
        processed = []
        for review in reviews[:10]:  # Limit to 10 most recent
            # Handle MapsReview objects
            processed.append(
                {
                    "place_name": getattr(review, "name", "Unknown"),
                    "rating": getattr(review, "rating", None),
                    "text": getattr(review, "text", ""),
                    "date": getattr(review, "relative_time_description", ""),
                    "location": getattr(review, "location", None),
                }
            )
        return processed

    def _process_photos(self, photos: list) -> list[dict]:
        """Process raw photo data"""
        processed = []
        for photo in photos[:10]:  # Limit to 10 most recent
            # Handle MapsPhoto objects
            processed.append(
                {
                    "url": getattr(photo, "url", ""),
                    "location": getattr(photo, "location", None),
                    "timestamp": getattr(photo, "timestamp", None),
                }
            )
        return processed
