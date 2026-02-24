"""Locations analyzer - unique locations, home country, foreign travel."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from typing import TYPE_CHECKING

from app.profiler.models.artifact import ProfilerArtifact
from app.profiler.models.entities.location_entity import LocationEntity

if TYPE_CHECKING:
    from app.profiler.models.job import ProfilerJob
    from app.profiler.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)


class LocationsAnalyzer:
    async def analyze(
        self,
        job: ProfilerJob,
        inference_client: InferenceClient,
    ) -> ProfilerArtifact | None:
        locations = await LocationEntity.find(
            LocationEntity.target_id == job.target_id,
        ).to_list()

        if not locations:
            return None

        country_counts: Counter[str] = Counter()
        for loc in locations:
            if loc.country_code:
                country_counts[loc.country_code] += 1

        home_country = country_counts.most_common(1)[0][0] if country_counts else None

        unique: list[dict] = []
        seen_names: set[str] = set()
        for loc in locations:
            key = loc.location_name.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            unique.append(
                {
                    "name": loc.location_name,
                    "lat": loc.lat,
                    "lng": loc.lng,
                    "country_code": loc.country_code,
                    "first_seen": loc.first_seen_at.isoformat(),
                    "last_seen": loc.last_seen_at.isoformat(),
                }
            )

        foreign_locs = [
            loc
            for loc in locations
            if loc.country_code and home_country and loc.country_code != home_country
        ]
        trips = self._group_trips(foreign_locs)

        return ProfilerArtifact(
            org_id=job.org_id,
            case_id=job.case_id,
            target_id=job.target_id,
            job_id=job.id,
            artifact_type="locations",
            version="v1",
            payload={
                "home_country": home_country,
                "unique_locations": unique,
                "foreign_trips": trips,
                "total_locations": len(locations),
            },
        )

    def _group_trips(self, locs: list[LocationEntity]) -> list[dict]:
        if not locs:
            return []
        sorted_locs = sorted(locs, key=lambda loc: loc.first_seen_at)
        trips: list[dict] = []
        current_trip: list[LocationEntity] = [sorted_locs[0]]

        for loc in sorted_locs[1:]:
            prev = current_trip[-1]
            if (loc.first_seen_at - prev.last_seen_at) <= timedelta(days=1):
                current_trip.append(loc)
            else:
                trips.append(self._trip_summary(current_trip))
                current_trip = [loc]

        if current_trip:
            trips.append(self._trip_summary(current_trip))
        return trips

    def _trip_summary(self, locs: list[LocationEntity]) -> dict:
        countries = list({loc.country_code for loc in locs if loc.country_code})
        names = list({loc.location_name for loc in locs})
        start = min(loc.first_seen_at for loc in locs)
        end = max(loc.last_seen_at for loc in locs)
        return {
            "countries": countries,
            "locations": names,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": max(1, (end - start).days + 1),
        }
