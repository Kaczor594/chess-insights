"""Shared utilities for one-time backfill scripts."""

import sqlite3
import sys
from pathlib import Path
from typing import Callable

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chess_insights.db"
BATCH_SIZE = 500


def get_connection() -> sqlite3.Connection:
    """Open a connection to the chess_insights database, or exit if missing."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    return conn


def run_backfill(
    conn: sqlite3.Connection,
    game_ids: list[int],
    process_game: Callable[[sqlite3.Connection, int], tuple[int, int]],
    label: str,
) -> tuple[int, int]:
    """Run a backfill across games with batch commits and progress reporting.

    Args:
        conn: Open database connection.
        game_ids: List of game IDs to process.
        process_game: Function(conn, game_id) -> (updated_count, error_count).
        label: Human-readable label for progress messages.

    Returns:
        (total_updated, total_errors)
    """
    total_games = len(game_ids)
    if total_games == 0:
        print(f"No games need {label} backfill.")
        return 0, 0

    print(f"Backfilling {label} for {total_games} games...")

    total_updated = 0
    total_errors = 0

    for i, game_id in enumerate(game_ids):
        updated, errors = process_game(conn, game_id)
        total_updated += updated
        total_errors += errors

        if (i + 1) % BATCH_SIZE == 0:
            conn.commit()
            print(f"  Progress: {i + 1}/{total_games} games, {total_updated} moves updated, {total_errors} errors")

    conn.commit()
    return total_updated, total_errors
