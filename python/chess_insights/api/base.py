"""Base class for chess platform API clients."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Optional


@dataclass
class GameData:
    """Standardized game data from any platform."""
    platform: str
    platform_game_id: str
    white_username: str
    black_username: str
    white_rating: Optional[int]
    black_rating: Optional[int]
    time_control: Optional[str]
    time_control_seconds: Optional[int]
    increment_seconds: Optional[int]
    date_played: Optional[str]
    result: Optional[str]
    termination_reason: Optional[str]
    eco_code: Optional[str]
    opening_name: Optional[str]
    url: Optional[str]
    pgn: str


class ChessApiClient(ABC):
    """Abstract base class for chess platform API clients."""

    @property
    @abstractmethod
    def platform(self) -> str:
        """Return the platform identifier."""
        pass

    @abstractmethod
    def fetch_games(
        self,
        username: str,
        since_timestamp: Optional[str] = None,
    ) -> Iterator[GameData]:
        """
        Fetch games for a user.

        Args:
            username: The username to fetch games for
            since_timestamp: Only fetch games after this timestamp (ISO format)

        Yields:
            GameData objects for each game
        """
        pass

    @abstractmethod
    def get_latest_game_timestamp(self, username: str) -> Optional[str]:
        """Get the timestamp of the user's most recent game."""
        pass
