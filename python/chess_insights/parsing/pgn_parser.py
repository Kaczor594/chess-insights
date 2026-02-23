"""PGN parsing utilities."""

import io
from dataclasses import dataclass
from typing import Optional

import chess
import chess.pgn


@dataclass
class ParsedMove:
    """A parsed move from a PGN."""
    ply_number: int
    color: str
    san: str
    uci: str
    comment: Optional[str]
    board_before: chess.Board
    board_after: chess.Board


@dataclass
class ParsedGame:
    """A fully parsed game from PGN."""
    moves: list[ParsedMove]
    headers: dict[str, str]


def parse_pgn(pgn_string: str) -> Optional[ParsedGame]:
    """
    Parse a PGN string into structured data.

    Returns:
        ParsedGame with all moves and headers, or None if parsing fails
    """
    pgn_io = io.StringIO(pgn_string)
    game = chess.pgn.read_game(pgn_io)

    if game is None:
        return None

    headers = dict(game.headers)
    moves = []
    board = game.board()
    ply = 0

    for node in game.mainline():
        move = node.move
        board_before = board.copy()

        san = board.san(move)
        uci = move.uci()
        board.push(move)

        color = "white" if ply % 2 == 0 else "black"
        comment = node.comment if node.comment else None

        moves.append(ParsedMove(
            ply_number=ply,
            color=color,
            san=san,
            uci=uci,
            comment=comment,
            board_before=board_before,
            board_after=board.copy(),
        ))

        ply += 1

    return ParsedGame(moves=moves, headers=headers)


def get_moves_with_comments(pgn_string: str) -> list[tuple[str, str]]:
    """
    Extract moves with their associated comments from a PGN.

    Returns:
        List of (san, comment) tuples
    """
    parsed = parse_pgn(pgn_string)
    if parsed is None:
        return []

    return [(m.san, m.comment or "") for m in parsed.moves]
