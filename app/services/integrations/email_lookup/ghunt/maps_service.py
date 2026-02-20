from __future__ import annotations

import logging
from typing import Any

import httpx
from ghunt.helpers.gmaps import get_reviews

# Patch must be applied BEFORE importing get_reviews so the local binding captures the patched version
from app.services.integrations.email_lookup.ghunt import gmaps_patch  # noqa: F401
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
        logger.info(
            f"GHuntMapsService: Starting get_maps_reviews for gaia_id={gaia_id}"
        )

        # Verify patch is applied
        import ghunt.helpers.gmaps as gmaps_module

        current_get_reviews = getattr(gmaps_module, "get_reviews", None)
        if current_get_reviews and hasattr(current_get_reviews, "_ghunt_patched"):
            logger.debug("GHuntMapsService: Verified gmaps patch is applied")
        else:
            logger.warning(
                "GHuntMapsService: gmaps patch may not be applied! "
                f"get_reviews={current_get_reviews}"
            )

        try:
            async with httpx.AsyncClient() as client:
                logger.debug(
                    f"GHuntMapsService: Calling get_reviews(client, {gaia_id})"
                )
                # get_reviews returns: (error_status, stats, reviews, photos)
                error_status, stats, reviews, photos = await get_reviews(
                    client, gaia_id
                )

                logger.info(
                    f"GHuntMapsService: get_reviews returned - "
                    f"error_status={error_status}, "
                    f"stats={stats}, "
                    f"reviews_count={len(reviews) if reviews else 0}, "
                    f"photos_count={len(photos) if photos else 0}"
                )

                if error_status == "failed":
                    logger.warning(
                        "GHuntMapsService: get_reviews returned 'failed' status"
                    )
                    return {"found": False, "error": "Failed to fetch reviews"}
                if error_status == "empty" or not reviews:
                    logger.info(
                        f"GHuntMapsService: No reviews found - "
                        f"error_status={error_status}, reviews={reviews}"
                    )
                    return {"found": False, "error": "No reviews found"}

                # Calculate photos stats from photos list
                photos_stats = {
                    "total_photos": len(photos),
                    "photos_with_location": sum(
                        1 for p in photos if hasattr(p, "location") and p.location
                    ),
                }

                logger.info(
                    f"GHuntMapsService: Successfully processed reviews - "
                    f"total_reviews={len(reviews)}, total_photos={len(photos)}"
                )

                return {
                    "found": True,
                    "total_reviews": len(reviews),
                    "reviews_stats": stats,
                    "photos_stats": photos_stats,
                    "reviews": self._process_reviews(reviews),
                    "photos": self._process_photos(photos),
                }
        except Exception as e:
            logger.error(
                f"GHuntMapsService: Exception in get_maps_reviews for gaia_id={gaia_id}: {e}",
                exc_info=True,
            )
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
