from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from ghunt.apis.calendar import CalendarHttp

from app.services.integrations.email_lookup.ghunt.credentials_manager import (
    GHuntCredentialsManager,
)

logger = logging.getLogger(__name__)


class GHuntCalendarService:
    """Service for GHunt Calendar API integration"""

    def __init__(self):
        self.name = "GHuntCalendarService"
        self._creds = None
        self._calendar_api = None

    def _get_credentials(self):
        """Get GHunt credentials"""
        if self._creds is None:
            self._creds = GHuntCredentialsManager.get_credentials()
        return self._creds

    def _get_calendar_api(self):
        """Get Calendar API instance"""
        if self._calendar_api is None:
            creds = self._get_credentials()
            self._calendar_api = CalendarHttp(creds)
        return self._calendar_api

    async def get_public_events(
        self, calendar_id: str, max_results: int = 10
    ) -> dict[str, Any]:
        """Get public events from a Google Calendar"""
        try:
            calendar_api = self._get_calendar_api()

            async with httpx.AsyncClient() as client:
                # Get events for the next 30 days
                time_min = datetime.utcnow().isoformat() + "Z"
                time_max = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"

                events = await calendar_api.get_events(
                    client,
                    calendar_id,
                    time_min=time_min,
                    time_max=time_max,
                    max_results=max_results,
                )

                if not events:
                    return {"found": False, "events": []}

                return {
                    "found": True,
                    "calendar_id": calendar_id,
                    "events": self._process_events(events),
                }
        except Exception as e:
            logger.error(f"GHunt Calendar API error: {e}")
            return {"found": False, "error": str(e)}

    def _process_events(self, events: list[dict]) -> list[dict]:
        """Process calendar events"""
        processed = []
        for event in events:
            processed.append(
                {
                    "id": event.get("id"),
                    "summary": event.get("summary"),
                    "description": event.get("description"),
                    "start": event.get("start", {}).get("dateTime")
                    or event.get("start", {}).get("date"),
                    "end": event.get("end", {}).get("dateTime")
                    or event.get("end", {}).get("date"),
                    "location": event.get("location"),
                    "organizer": event.get("organizer", {}).get("email"),
                }
            )
        return processed
