#!/usr/bin/env python3
"""One-time backfill script to populate best_move_san for existing moves.

Replays each game using python-chess to convert the existing best_move (UCI)
into standard algebraic notation (SAN). No Stockfish needed — just board
replay and move conversion.

Usage:
    python3 scripts/backfill_best_move_san.py
"""

import sqlite3

import chess

from backfill_utils import get_connection, run_backfill


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

        try:
            actual_move = chess.Move.from_uci(uci)
            board.push(actual_move)
        except (ValueError, chess.InvalidMoveError, AssertionError):
            break

    return updated, errors


def main():
    conn = get_connection()

    game_ids = get_games_needing_backfill(conn)
    total_updated, total_errors = run_backfill(conn, game_ids, backfill_game, "best_move_san")

    if total_updated or total_errors:
        cursor = conn.execute("SELECT COUNT(*) FROM moves WHERE best_move_san IS NULL AND best_move IS NOT NULL")
        remaining_nulls = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM moves WHERE best_move_san LIKE '?%'")
        flagged = cursor.fetchone()[0]

        print(f"\nBackfill complete:")
        print(f"  Games processed: {len(game_ids)}")
        print(f"  Moves updated: {total_updated}")
        print(f"  Errors (flagged with '?'): {total_errors}")
        print(f"  Remaining NULLs (with best_move): {remaining_nulls}")
        print(f"  Total '?'-prefixed rows: {flagged}")

    conn.close()


if __name__ == "__main__":
    main()
