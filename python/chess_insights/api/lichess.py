"""Lichess API client."""

import json
import re
import time
from datetime import datetime
from typing import Iterator, Optional

import requests

from .base import ChessApiClient, GameData


class LichessClient(ChessApiClient):
    """Lichess API client using NDJSON streaming."""

    BASE_URL = "https://lichess.org/api"

    def __init__(self, user_agent: str = "chess-insights/1.0", delay: float = 0.3):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/x-ndjson",
        })
        self.delay = delay
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    @property
    def platform(self) -> str:
        return "lichess"

    def _parse_time_control(self, speed: str, clock: Optional[dict]) -> tuple[Optional[int], Optional[int], str]:
        """Parse time control from Lichess game data."""
        if clock:
            initial = clock.get("initial", 0)
            increment = clock.get("increment", 0)
            time_control_str = f"{initial}+{increment}"
            return initial, increment, time_control_str
        return None, None, speed

    def _parse_result(self, winner: Optional[str], status: str) -> Optional[str]:
        """Parse game result."""
        if status in ("draw", "stalemate"):
            return "1/2-1/2"
        if winner == "white":
            return "1-0"
        if winner == "black":
            return "0-1"
        if status in ("outoftime", "resign", "mate"):
            return "*"  # Should have winner but didn't
        return "1/2-1/2" if status == "draw" else "*"

    def _parse_termination(self, status: str) -> Optional[str]:
        """Parse termination reason."""
        status_map = {
            "mate": "checkmate",
            "resign": "resignation",
            "outoftime": "timeout",
            "stalemate": "stalemate",
            "draw": "agreement",
            "timeout": "timeout",
            "cheat": "abandoned",
            "noStart": "abandoned",
            "unknownFinish": None,
            "variantEnd": "variant",
        }
        return status_map.get(status, status)

    def _extract_pgn_header(self, pgn: str, header: str) -> Optional[str]:
        """Extract a header value from PGN."""
        match = re.search(rf'\[{header} "([^"]+)"\]', pgn)
        return match.group(1) if match else None

    def _parse_game(self, game: dict) -> Optional[GameData]:
        """Parse a game from the API response."""
        pgn = game.get("pgn")
        if not pgn:
            return None

        players = game.get("players", {})
        white = players.get("white", {})
        black = players.get("black", {})

        clock = game.get("clock")
        base_seconds, increment, time_control = self._parse_time_control(
            game.get("speed", ""), clock
        )

        # Parse timestamp
        created_at = game.get("createdAt")
        date_played = None
        if created_at:
            date_played = datetime.utcfromtimestamp(created_at / 1000).isoformat()

        # Extract ECO and opening
        eco_code = self._extract_pgn_header(pgn, "ECO")
        opening = game.get("opening", {})
        opening_name = opening.get("name")

        # Handle AI opponents (aiLevel is an integer)
        white_user = white.get("user", {})
        black_user = black.get("user", {})
        white_name = white_user.get("name") if white_user else None
        black_name = black_user.get("name") if black_user else None

        if not white_name:
            ai_level = white.get("aiLevel")
            white_name = f"AI-Level-{ai_level}" if ai_level else "AI"
        if not black_name:
            ai_level = black.get("aiLevel")
            black_name = f"AI-Level-{ai_level}" if ai_level else "AI"

        return GameData(
            platform="lichess",
            platform_game_id=game.get("id", ""),
            white_username=white_name,
            black_username=black_name,
            white_rating=white.get("rating"),
            black_rating=black.get("rating"),
            time_control=time_control,
            time_control_seconds=base_seconds,
            increment_seconds=increment,
            date_played=date_played,
            result=self._parse_result(game.get("winner"), game.get("status", "")),
            termination_reason=self._parse_termination(game.get("status", "")),
            eco_code=eco_code,
            opening_name=opening_name,
            url=f"https://lichess.org/{game.get('id', '')}",
            pgn=pgn,
        )

    def fetch_games(
        self,
        username: str,
        since_timestamp: Optional[str] = None,
    ) -> Iterator[GameData]:
        """Fetch games for a user from Lichess using NDJSON streaming."""
        self._rate_limit()

        params = {
            "pgnInJson": "true",
            "clocks": "true",
            "evals": "false",
            "opening": "true",
        }

        if since_timestamp:
            since_dt = datetime.fromisoformat(since_timestamp.replace("Z", "+00:00"))
            # Lichess uses milliseconds
            params["since"] = int(since_dt.timestamp() * 1000)

        url = f"{self.BASE_URL}/games/user/{username}"

        try:
            response = self.session.get(url, params=params, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        game = json.loads(line.decode("utf-8"))
                        game_data = self._parse_game(game)
                        if game_data:
                            yield game_data
                    except json.JSONDecodeError:
                        continue

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return
            raise

    def get_latest_game_timestamp(self, username: str) -> Optional[str]:
        """Get the timestamp of the user's most recent game."""
        self._rate_limit()

        url = f"{self.BASE_URL}/games/user/{username}"
        params = {
            "max": 1,
            "pgnInJson": "false",
        }

        try:
            response = self.session.get(url, params=params, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        game = json.loads(line.decode("utf-8"))
                        created_at = game.get("createdAt")
                        if created_at:
                            return datetime.utcfromtimestamp(created_at / 1000).isoformat()
                    except json.JSONDecodeError:
                        continue
                    break

        except requests.HTTPError:
            pass

        return None
