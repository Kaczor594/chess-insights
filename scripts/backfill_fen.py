#!/usr/bin/env python3
"""One-time backfill script to populate fen for existing moves.

Replays each game's PGN using python-chess to capture the board FEN before
each move was played. No Stockfish needed — just PGN replay.

Usage:
    python3 scripts/backfill_fen.py
"""

import io
import sqlite3

import chess
import chess.pgn

from backfill_utils import get_connection, run_backfill


def get_games_needing_backfill(conn: sqlite3.Connection) -> list[int]:
    """Get game_ids that have at least one move with NULL fen."""
    cursor = conn.execute("""
        SELECT DISTINCT game_id FROM moves
        WHERE fen IS NULL
        ORDER BY game_id
    """)
    return [row[0] for row in cursor.fetchall()]


def backfill_game(conn: sqlite3.Connection, game_id: int) -> tuple[int, int]:
    """Backfill fen for a single game by replaying its PGN.

    Returns (updated_count, error_count).
    """
    cursor = conn.execute("SELECT pgn FROM games WHERE game_id = ?", (game_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return 0, 0

    game = chess.pgn.read_game(io.StringIO(row[0]))
    if game is None:
        return 0, 1

    board = game.board()
    ply = 0
    updated = 0
    errors = 0

    for node in game.mainline():
        fen_before = board.fen()

        result = conn.execute(
            "UPDATE moves SET fen = ? WHERE game_id = ? AND ply_number = ?",
            (fen_before, game_id, ply)
        )
        if result.rowcount > 0:
            updated += 1

        try:
            board.push(node.move)
        except (ValueError, AssertionError):
            errors += 1
            break

        ply += 1

    return updated, errors


def main():
    conn = get_connection()

    # Add the column if it doesn't exist yet
    try:
        conn.execute("ALTER TABLE moves ADD COLUMN fen TEXT")
        conn.commit()
        print("Added 'fen' column to moves table.")
    except sqlite3.OperationalError:
        pass

    game_ids = get_games_needing_backfill(conn)
    total_updated, total_errors = run_backfill(conn, game_ids, backfill_game, "fen")

    if total_updated or total_errors:
        cursor = conn.execute("SELECT COUNT(*) FROM moves WHERE fen IS NULL")
        remaining_nulls = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM moves WHERE fen IS NOT NULL")
        populated = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM moves")
        total_moves = cursor.fetchone()[0]

        print(f"\nBackfill complete:")
        print(f"  Games processed: {len(game_ids)}")
        print(f"  Moves updated: {total_updated}")
        print(f"  Errors: {total_errors}")
        print(f"  Populated: {populated}/{total_moves} ({100 * populated / total_moves:.1f}%)")
        print(f"  Remaining NULLs: {remaining_nulls}")

    conn.close()


if __name__ == "__main__":
    main()
