"""Configuration loading for chess-insights."""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class StockfishConfig:
    """Stockfish engine configuration."""
    path: str = "/Users/isaackaczor/Downloads/stockfish/stockfish-macos-m1-apple-silicon"
    default_depth: int = 15
    threads: int = 4
    hash_mb: int = 256
    centipawn_cap: int = 9999


@dataclass
class ApiConfig:
    """API client configuration."""
    chesscom_delay: float = 0.5
    lichess_delay: float = 0.3
    user_agent: str = "chess-insights/1.0"


@dataclass
class Config:
    """Main configuration class."""
    database_path: Path = field(default_factory=lambda: Path("data/chess_insights.db"))
    stockfish: StockfishConfig = field(default_factory=StockfishConfig)
    api: ApiConfig = field(default_factory=ApiConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file or use defaults."""
        config = cls()

        if config_path is None:
            # Try to find config.yaml in the project root
            possible_paths = [
                Path("config.yaml"),
                Path(__file__).parent.parent.parent / "config.yaml",
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = path
                    break

        if config_path and config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}

            if "database_path" in data:
                config.database_path = Path(data["database_path"])

            if "stockfish" in data:
                sf_data = data["stockfish"]
                config.stockfish = StockfishConfig(
                    path=sf_data.get("path", config.stockfish.path),
                    default_depth=sf_data.get("default_depth", config.stockfish.default_depth),
                    threads=sf_data.get("threads", config.stockfish.threads),
                    hash_mb=sf_data.get("hash_mb", config.stockfish.hash_mb),
                    centipawn_cap=sf_data.get("centipawn_cap", config.stockfish.centipawn_cap),
                )

            if "api" in data:
                api_data = data["api"]
                config.api = ApiConfig(
                    chesscom_delay=api_data.get("chesscom_delay", config.api.chesscom_delay),
                    lichess_delay=api_data.get("lichess_delay", config.api.lichess_delay),
                    user_agent=api_data.get("user_agent", config.api.user_agent),
                )

        return config

    def get_absolute_db_path(self, base_path: Path) -> Path:
        """Get the absolute database path relative to a base path."""
        if self.database_path.is_absolute():
            return self.database_path
        return base_path / self.database_path
