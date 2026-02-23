"""Chess.com API client."""

import re
import time
from datetime import datetime
from typing import Iterator, Optional

import requests

from .base import ChessApiClient, GameData


class ChesscomClient(ChessApiClient):
    """Chess.com API client."""

    BASE_URL = "https://api.chess.com/pub"

    def __init__(self, user_agent: str = "chess-insights/1.0", delay: float = 0.5):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.delay = delay
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str) -> dict:
        """Make a rate-limited GET request."""
        self._rate_limit()
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    @property
    def platform(self) -> str:
        return "chesscom"

    def _get_archives(self, username: str) -> list[str]:
        """Get list of monthly archive URLs for a user."""
        url = f"{self.BASE_URL}/player/{username}/games/archives"
        data = self._get(url)
        return data.get("archives", [])

    def _parse_time_control(self, time_control: str) -> tuple[Optional[int], Optional[int]]:
        """Parse time control string into base seconds and increment."""
        if not time_control or time_control == "-":
            return None, None

        try:
            # Format: "600" or "600+5" or "1/86400" (daily)
            if "/" in time_control:
                # Daily game format
                parts = time_control.split("/")
                return int(parts[1]), 0

            if "+" in time_control:
                parts = time_control.split("+")
                return int(parts[0]), int(parts[1])

            return int(time_control), 0
        except (ValueError, IndexError):
            return None, None

    def _extract_game_id(self, url: str) -> str:
        """Extract game ID from Chess.com game URL."""
        # URLs look like https://www.chess.com/game/live/12345678
        match = re.search(r"/game/(?:live|daily)/(\d+)", url)
        if match:
            return match.group(1)
        return url  # Fallback to full URL

    def _parse_result(self, white_result: str, black_result: str) -> Optional[str]:
        """Parse game result from player results."""
        if white_result == "win":
            return "1-0"
        elif black_result == "win":
            return "0-1"
        elif white_result in ("draw", "stalemate", "insufficient", "50move", "repetition", "agreed"):
            return "1/2-1/2"
        elif black_result in ("draw", "stalemate", "insufficient", "50move", "repetition", "agreed"):
            return "1/2-1/2"
        return "*"

    def _parse_termination(self, white_result: str, black_result: str) -> Optional[str]:
        """Determine termination reason."""
        results = [white_result, black_result]
        if "timeout" in results:
            return "timeout"
        if "resigned" in results:
            return "resignation"
        if "checkmated" in results:
            return "checkmate"
        if "stalemate" in results:
            return "stalemate"
        if "insufficient" in results:
            return "insufficient"
        if "50move" in results:
            return "50move"
        if "repetition" in results:
            return "repetition"
        if "agreed" in results:
            return "agreement"
        if "abandoned" in results:
            return "abandoned"
        return None

    def _parse_game(self, game: dict) -> Optional[GameData]:
        """Parse a game from the API response."""
        pgn = game.get("pgn")
        if not pgn:
            return None

        white = game.get("white", {})
        black = game.get("black", {})

        time_control = game.get("time_control", "")
        base_seconds, increment = self._parse_time_control(time_control)

        # Parse end_time to ISO format
        end_time = game.get("end_time")
        date_played = None
        if end_time:
            date_played = datetime.utcfromtimestamp(end_time).isoformat()

        # Extract ECO and opening from PGN headers
        eco_code = None
        opening_name = None
        eco_match = re.search(r'\[ECO "([^"]+)"\]', pgn)
        if eco_match:
            eco_code = eco_match.group(1)
        opening_match = re.search(r'\[ECOUrl "[^"]*?/([^/"]+)"\]', pgn)
        if opening_match:
            opening_name = opening_match.group(1).replace("-", " ").title()

        return GameData(
            platform="chesscom",
            platform_game_id=self._extract_game_id(game.get("url", "")),
            white_username=white.get("username", ""),
            black_username=black.get("username", ""),
            white_rating=white.get("rating"),
            black_rating=black.get("rating"),
            time_control=time_control,
            time_control_seconds=base_seconds,
            increment_seconds=increment,
            date_played=date_played,
            result=self._parse_result(
                white.get("result", ""),
                black.get("result", "")
            ),
            termination_reason=self._parse_termination(
                white.get("result", ""),
                black.get("result", "")
            ),
            eco_code=eco_code,
            opening_name=opening_name,
            url=game.get("url"),
            pgn=pgn,
        )

    def fetch_games(
        self,
        username: str,
        since_timestamp: Optional[str] = None,
    ) -> Iterator[GameData]:
        """Fetch games for a user from Chess.com."""
        archives = self._get_archives(username)

        # Filter archives if we have a since_timestamp
        if since_timestamp:
            since_dt = datetime.fromisoformat(since_timestamp.replace("Z", "+00:00"))
            since_month = f"{since_dt.year}/{since_dt.month:02d}"
            archives = [a for a in archives if a.split("/")[-2] + "/" + a.split("/")[-1] >= since_month]

        for archive_url in archives:
            try:
                data = self._get(archive_url)
                games = data.get("games", [])

                for game in games:
                    # Filter by timestamp if needed
                    if since_timestamp:
                        end_time = game.get("end_time")
                        if end_time:
                            game_dt = datetime.utcfromtimestamp(end_time)
                            if game_dt <= since_dt:
                                continue

                    game_data = self._parse_game(game)
                    if game_data:
                        yield game_data

            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    continue
                raise

    def get_latest_game_timestamp(self, username: str) -> Optional[str]:
        """Get the timestamp of the user's most recent game."""
        archives = self._get_archives(username)
        if not archives:
            return None

        # Get the most recent archive
        latest_archive = archives[-1]
        try:
            data = self._get(latest_archive)
            games = data.get("games", [])
            if games:
                latest_game = max(games, key=lambda g: g.get("end_time", 0))
                end_time = latest_game.get("end_time")
                if end_time:
                    return datetime.utcfromtimestamp(end_time).isoformat()
        except requests.HTTPError:
            pass

        return None
