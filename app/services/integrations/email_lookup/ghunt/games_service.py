from __future__ import annotations

import logging
from typing import Any

import httpx
from ghunt.apis.playgames import PlayGames

from app.services.integrations.email_lookup.ghunt.credentials_manager import (
    GHuntCredentialsManager,
)

logger = logging.getLogger(__name__)


class GHuntGamesService:
    """Service for GHunt Play Games integration"""

    def __init__(self):
        self.name = "GHuntGamesService"
        self._creds = None
        self._games_api = None

    def _get_credentials(self):
        """Get GHunt credentials"""
        if self._creds is None:
            self._creds = GHuntCredentialsManager.get_credentials()
        return self._creds

    def _get_games_api(self):
        """Get Play Games API instance"""
        if self._games_api is None:
            creds = self._get_credentials()
            self._games_api = PlayGames(creds)
        return self._games_api

    async def get_player_profile(self, player_id: str) -> dict[str, Any]:
        """Get Play Games player profile"""
        try:
            games_api = self._get_games_api()

            async with httpx.AsyncClient() as client:
                await games_api.oauth_consent(client)
                profile = await games_api.get_player(client, player_id)

                if not profile:
                    return {"found": False, "error": "Player not found"}

                return {
                    "found": True,
                    "player_id": profile.player_id,
                    "display_name": profile.display_name,
                    "avatar_url": profile.avatar_url,
                    "title": profile.title,
                    "level": profile.level,
                    "total_xp": profile.total_xp,
                }
        except Exception as e:
            logger.error(f"GHunt Play Games API error: {e}")
            return {"found": False, "error": str(e)}

    async def get_player_games(self, player_id: str) -> dict[str, Any]:
        """Get games played by a player"""
        try:
            games_api = self._get_games_api()

            async with httpx.AsyncClient() as client:
                await games_api.oauth_consent(client)
                games = await games_api.get_player_games(client, player_id)

                if not games:
                    return {"found": False, "games": []}

                return {
                    "found": True,
                    "total_games": len(games.items),
                    "games": [
                        {
                            "name": game.name,
                            "icon_url": game.icon_url,
                            "last_played": game.last_played_timestamp,
                            "achievements_unlocked": game.achievements_unlocked,
                            "achievements_total": game.achievements_total,
                        }
                        for game in games.items[:10]  # Limit to 10
                    ],
                }
        except Exception as e:
            logger.error(f"GHunt Play Games API error: {e}")
            return {"found": False, "error": str(e)}
