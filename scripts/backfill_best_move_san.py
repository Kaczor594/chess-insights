#!/usr/bin/env python3
"""One-time backfill script to populate best_move_san for existing moves.

Replays each game using python-chess to convert the existing best_move (UCI)
into standard algebraic notation (SAN). No Stockfish needed — just board
replay and move conversion.

Usage:
    python3 scripts/backfill_best_move_san.py
"""

import sqlite3
import sys
from pathlib import Path

import chess


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "chess_insights.db"
BATCH_SIZE = 500


def get_games_needing_backfill(conn: sqlite3.Connection) -> list[int]:
    """Get game_ids that have at least one move with NULL best_move_san."""
    cursor = conn.execute("""
        SELECT DISTINCT game_id FROM moves
        WHERE best_move_san IS NULL AND best_move IS NOT NULL
        ORDER BY game_id
    """)
    return [row[0] for row in cursor.fetchall()]


def backfill_game(conn: sqlite3.Connection, game_id: int) -> tuple[int, int]:
    """Backfill best_move_san for a single game.

    Returns (updated_count, error_count).
    """
    cursor = conn.execute("""
        SELECT move_id, ply_number, uci, best_move
        FROM moves
        WHERE game_id = ? AND best_move IS NOT NULL
        ORDER BY ply_number
    """, (game_id,))
    moves = cursor.fetchall()

    if not moves:
        return 0, 0

    board = chess.Board()
    updated = 0
    errors = 0

    for move_id, ply_number, uci, best_move_uci in moves:
        # Convert best_move UCI → SAN using current board state
        try:
            best_chess_move = chess.Move.from_uci(best_move_uci)
            if board.is_legal(best_chess_move):
                best_move_san = board.san(best_chess_move)
            else:
                best_move_san = f"?{best_move_uci}"
                errors += 1
        except (ValueError, chess.InvalidMoveError):
            best_move_san = f"?{best_move_uci}"
            errors += 1

        conn.execute(
            "UPDATE moves SET best_move_san = ? WHERE move_id = ?",
            (best_move_san, move_id)
        )
        updated += 1

        # Advance the board with the actual move played
        try:
            actual_move = chess.Move.from_uci(uci)
            board.push(actual_move)
        except (ValueError, chess.InvalidMoveError, AssertionError):
            # Can't continue replaying this game
            break

    return updated, errors


def main():
    db_path = DB_PATH
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    # Get games needing backfill
    game_ids = get_games_needing_backfill(conn)
    total_games = len(game_ids)

    if total_games == 0:
        print("No games need backfill — all best_move_san values are populated.")
        conn.close()
        return

    print(f"Backfilling {total_games} games...")

    total_updated = 0
    total_errors = 0

    for i, game_id in enumerate(game_ids):
        updated, errors = backfill_game(conn, game_id)
        total_updated += updated
        total_errors += errors

        # Batch commit
        if (i + 1) % BATCH_SIZE == 0:
            conn.commit()
            print(f"  Progress: {i + 1}/{total_games} games, {total_updated} moves updated, {total_errors} errors")

    conn.commit()

    # Verification
    cursor = conn.execute("SELECT COUNT(*) FROM moves WHERE best_move_san IS NULL AND best_move IS NOT NULL")
    remaining_nulls = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(*) FROM moves WHERE best_move_san LIKE '?%'")
    flagged = cursor.fetchone()[0]

    print(f"\nBackfill complete:")
    print(f"  Games processed: {total_games}")
    print(f"  Moves updated: {total_updated}")
    print(f"  Errors (flagged with '?'): {total_errors}")
    print(f"  Remaining NULLs (with best_move): {remaining_nulls}")
    print(f"  Total '?'-prefixed rows: {flagged}")

    conn.close()


if __name__ == "__main__":
    main()
