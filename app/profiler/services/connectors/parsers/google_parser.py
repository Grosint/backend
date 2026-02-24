"""Google (Maps/Reviews) HTML parser - v1 minimal extraction."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.profiler.services.connectors.parsers import (
    ParseResult,
    extract_json_ld,
    extract_og_meta,
    strip_html_tags,
)

logger = logging.getLogger(__name__)

SOURCE = "google"


class GoogleParser:
    """Extract canonical entities from Google Maps/reviews HTML."""

    def parse(self, html: str, url: str) -> ParseResult:
        result = ParseResult()
        og = extract_og_meta(html)
        json_ld = extract_json_ld(html)

        for ld in json_ld:
            ld_type = ld.get("@type", "")
            if ld_type in ("LocalBusiness", "Restaurant", "Place", "Store"):
                place_name = ld.get("name", og.get("title", ""))
                category = ld_type
                self._extract_reviews_from_ld(ld, place_name, category, result)

                geo = ld.get("geo", {})
                addr = ld.get("address", {})
                if place_name:
                    result.locations.append(
                        {
                            "source": SOURCE,
                            "location_name": place_name,
                            "lat": self._safe_float(geo.get("latitude")),
                            "lng": self._safe_float(geo.get("longitude")),
                            "country_code": addr.get("addressCountry"),
                        }
                    )

            if ld_type == "Review":
                self._parse_single_review(ld, result)

        if not result.reviews:
            self._extract_reviews_from_text(html, og, result)

        logger.debug(
            "Google parse complete",
            extra={"url": url[:80], "reviews": len(result.reviews)},
        )
        return result

    def _extract_reviews_from_ld(
        self,
        ld: dict,
        place_name: str,
        category: str,
        result: ParseResult,
    ) -> None:
        reviews = ld.get("review", [])
        if isinstance(reviews, dict):
            reviews = [reviews]
        for rev in reviews:
            rating_obj = rev.get("reviewRating", {})
            result.reviews.append(
                {
                    "place_name": place_name,
                    "category": category,
                    "rating": self._safe_float(rating_obj.get("ratingValue")),
                    "price_range": ld.get("priceRange"),
                    "review_text": rev.get("reviewBody", ""),
                }
            )

    def _parse_single_review(self, ld: dict, result: ParseResult) -> None:
        item = ld.get("itemReviewed", {})
        rating_obj = ld.get("reviewRating", {})
        result.reviews.append(
            {
                "place_name": item.get("name", ""),
                "category": item.get("@type", ""),
                "rating": self._safe_float(rating_obj.get("ratingValue")),
                "price_range": None,
                "review_text": ld.get("reviewBody", ""),
            }
        )

    def _extract_reviews_from_text(
        self,
        html: str,
        og: dict[str, str],
        result: ParseResult,
    ) -> None:
        text = strip_html_tags(html)
        rating_pattern = re.compile(
            r"(\d(?:\.\d)?)\s*(?:out of 5|stars?|/5)", re.IGNORECASE
        )
        for match in rating_pattern.finditer(text):
            result.reviews.append(
                {
                    "place_name": og.get("title", ""),
                    "category": "",
                    "rating": float(match.group(1)),
                    "price_range": None,
                    "review_text": "",
                }
            )

    def _safe_float(self, val: Any) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
