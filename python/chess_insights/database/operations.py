"""Database operations for chess-insights."""

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from .schema import get_schema


class DatabaseManager:
    """Manages SQLite database operations for chess-insights."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Get a database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Initialize the database with the schema."""
        with self.get_connection() as conn:
            conn.executescript(get_schema())

    def get_or_create_player(self, username: str, platform: str) -> int:
        """Get or create a player and return the player_id."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT player_id FROM players WHERE username = ? AND platform = ?",
                (username.lower(), platform)
            )
            row = cursor.fetchone()
            if row:
                return row["player_id"]

            cursor = conn.execute(
                "INSERT INTO players (username, platform) VALUES (?, ?)",
                (username.lower(), platform)
            )
            return cursor.lastrowid

    def game_exists(self, platform: str, platform_game_id: str) -> bool:
        """Check if a game already exists in the database."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM games WHERE platform = ? AND platform_game_id = ?",
                (platform, platform_game_id)
            )
            return cursor.fetchone() is not None

    def insert_game(
        self,
        platform: str,
        platform_game_id: str,
        white_player_id: int,
        black_player_id: int,
        white_rating: Optional[int],
        black_rating: Optional[int],
        time_control: Optional[str],
        time_control_seconds: Optional[int],
        increment_seconds: Optional[int],
        date_played: Optional[str],
        result: Optional[str],
        termination_reason: Optional[str],
        eco_code: Optional[str],
        opening_name: Optional[str],
        url: Optional[str],
        pgn: str,
    ) -> int:
        """Insert a new game and return the game_id."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO games (
                    platform, platform_game_id, white_player_id, black_player_id,
                    white_rating, black_rating, time_control, time_control_seconds,
                    increment_seconds, date_played, result, termination_reason,
                    eco_code, opening_name, url, pgn
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    platform, platform_game_id, white_player_id, black_player_id,
                    white_rating, black_rating, time_control, time_control_seconds,
                    increment_seconds, date_played, result, termination_reason,
                    eco_code, opening_name, url, pgn
                )
            )
            return cursor.lastrowid

    def get_pending_games(self, limit: Optional[int] = None) -> list[dict]:
        """Get games pending analysis."""
        with self.get_connection() as conn:
            query = """
                SELECT g.*,
                       pw.username as white_username,
                       pb.username as black_username
                FROM games g
                JOIN players pw ON g.white_player_id = pw.player_id
                JOIN players pb ON g.black_player_id = pb.player_id
                WHERE g.analysis_status = 'pending'
                ORDER BY g.date_played DESC
            """
            if limit:
                query += f" LIMIT {limit}"
            cursor = conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def update_game_analysis_status(
        self, game_id: int, status: str, depth: Optional[int] = None
    ) -> None:
        """Update the analysis status of a game."""
        with self.get_connection() as conn:
            if depth:
                conn.execute(
                    "UPDATE games SET analysis_status = ?, analysis_depth = ? WHERE game_id = ?",
                    (status, depth, game_id)
                )
            else:
                conn.execute(
                    "UPDATE games SET analysis_status = ? WHERE game_id = ?",
                    (status, game_id)
                )

    def insert_move(
        self,
        game_id: int,
        ply_number: int,
        color: str,
        san: str,
        uci: Optional[str] = None,
        clock_time_remaining: Optional[float] = None,
        time_spent: Optional[float] = None,
        pct_time_used: Optional[float] = None,
        eval_before: Optional[float] = None,
        eval_after: Optional[float] = None,
        centipawn_loss: Optional[float] = None,
        is_mate_before: bool = False,
        is_mate_after: bool = False,
        mate_in_n_before: Optional[int] = None,
        mate_in_n_after: Optional[int] = None,
        best_move: Optional[str] = None,
        best_move_san: Optional[str] = None,
        game_phase: Optional[str] = None,
        is_book_move: bool = False,
    ) -> int:
        """Insert a move record."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO moves (
                    game_id, ply_number, color, san, uci,
                    clock_time_remaining, time_spent, pct_time_used,
                    eval_before, eval_after, centipawn_loss,
                    is_mate_before, is_mate_after, mate_in_n_before, mate_in_n_after,
                    best_move, best_move_san, game_phase, is_book_move
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game_id, ply_number, color, san, uci,
                    clock_time_remaining, time_spent, pct_time_used,
                    eval_before, eval_after, centipawn_loss,
                    int(is_mate_before), int(is_mate_after), mate_in_n_before, mate_in_n_after,
                    best_move, best_move_san, game_phase, int(is_book_move)
                )
            )
            return cursor.lastrowid

    def insert_moves_batch(self, moves: list[dict]) -> None:
        """Insert multiple moves in a batch."""
        with self.get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO moves (
                    game_id, ply_number, color, san, uci,
                    clock_time_remaining, time_spent, pct_time_used,
                    eval_before, eval_after, centipawn_loss,
                    is_mate_before, is_mate_after, mate_in_n_before, mate_in_n_after,
                    best_move, best_move_san, game_phase, is_book_move
                ) VALUES (
                    :game_id, :ply_number, :color, :san, :uci,
                    :clock_time_remaining, :time_spent, :pct_time_used,
                    :eval_before, :eval_after, :centipawn_loss,
                    :is_mate_before, :is_mate_after, :mate_in_n_before, :mate_in_n_after,
                    :best_move, :best_move_san, :game_phase, :is_book_move
                )
                """,
                moves
            )

    def delete_moves_for_game(self, game_id: int) -> None:
        """Delete all moves for a game (for re-analysis)."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM moves WHERE game_id = ?", (game_id,))

    def get_sync_metadata(self, username: str, platform: str) -> Optional[dict]:
        """Get sync metadata for a user/platform combination."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM sync_metadata WHERE username = ? AND platform = ?",
                (username.lower(), platform)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def upsert_sync_metadata(
        self,
        username: str,
        platform: str,
        last_sync_timestamp: Optional[str] = None,
        last_game_timestamp: Optional[str] = None,
        games_fetched: int = 0,
    ) -> None:
        """Insert or update sync metadata."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sync_metadata (username, platform, last_sync_timestamp, last_game_timestamp, games_fetched)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(username, platform) DO UPDATE SET
                    last_sync_timestamp = COALESCE(excluded.last_sync_timestamp, last_sync_timestamp),
                    last_game_timestamp = COALESCE(excluded.last_game_timestamp, last_game_timestamp),
                    games_fetched = games_fetched + excluded.games_fetched
                """,
                (username.lower(), platform, last_sync_timestamp, last_game_timestamp, games_fetched)
            )

    def get_statistics(self) -> dict:
        """Get database statistics."""
        with self.get_connection() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) as count FROM games")
            stats["total_games"] = cursor.fetchone()["count"]

            cursor = conn.execute(
                "SELECT analysis_status, COUNT(*) as count FROM games GROUP BY analysis_status"
            )
            stats["by_status"] = {row["analysis_status"]: row["count"] for row in cursor.fetchall()}

            cursor = conn.execute("SELECT COUNT(*) as count FROM moves")
            stats["total_moves"] = cursor.fetchone()["count"]

            cursor = conn.execute("SELECT COUNT(*) as count FROM players")
            stats["total_players"] = cursor.fetchone()["count"]

            cursor = conn.execute(
                "SELECT platform, COUNT(*) as count FROM games GROUP BY platform"
            )
            stats["by_platform"] = {row["platform"]: row["count"] for row in cursor.fetchall()}

            return stats
