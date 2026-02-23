"""Stockfish engine wrapper for position analysis."""

from dataclasses import dataclass
from typing import Optional
from contextlib import contextmanager

import chess
import chess.engine

from ..config import StockfishConfig


@dataclass
class PositionAnalysis:
    """Analysis result for a single position."""
    eval_centipawns: Optional[float]  # Centipawn score (capped)
    is_mate: bool
    mate_in_n: Optional[int]  # Positive = white mates, negative = black mates
    best_move: Optional[str]  # Best move in UCI format
    best_move_san: Optional[str]  # Best move in SAN format


class StockfishAnalyzer:
    """Wrapper for Stockfish engine analysis."""

    def __init__(self, config: StockfishConfig):
        self.config = config
        self.engine: Optional[chess.engine.SimpleEngine] = None

    def start(self) -> None:
        """Start the Stockfish engine."""
        if self.engine is not None:
            return

        self.engine = chess.engine.SimpleEngine.popen_uci(self.config.path)
        self.engine.configure({
            "Threads": self.config.threads,
            "Hash": self.config.hash_mb,
        })

    def stop(self) -> None:
        """Stop the Stockfish engine."""
        if self.engine is not None:
            self.engine.quit()
            self.engine = None

    @contextmanager
    def session(self):
        """Context manager for engine session."""
        self.start()
        try:
            yield self
        finally:
            self.stop()

    def _score_to_centipawns(
        self, score: chess.engine.PovScore, turn: chess.Color
    ) -> tuple[Optional[float], bool, Optional[int]]:
        """
        Convert engine score to centipawns from white's perspective.

        Returns:
            (centipawns, is_mate, mate_in_n)
        """
        # Get score from white's perspective
        white_score = score.white()

        if white_score.is_mate():
            mate_in = white_score.mate()
            return None, True, mate_in

        cp = white_score.score()
        if cp is not None:
            # Cap the centipawn score
            cp = max(-self.config.centipawn_cap, min(self.config.centipawn_cap, cp))
            return float(cp), False, None

        return None, False, None

    def analyze_position(
        self, board: chess.Board, depth: Optional[int] = None
    ) -> PositionAnalysis:
        """
        Analyze a single position.

        Args:
            board: The chess position to analyze
            depth: Analysis depth (uses config default if not specified)

        Returns:
            PositionAnalysis with evaluation and best move
        """
        if self.engine is None:
            raise RuntimeError("Engine not started. Call start() first or use session().")

        analysis_depth = depth or self.config.default_depth

        info = self.engine.analyse(board, chess.engine.Limit(depth=analysis_depth))

        # Extract score
        score = info.get("score")
        eval_cp, is_mate, mate_in_n = None, False, None
        if score:
            eval_cp, is_mate, mate_in_n = self._score_to_centipawns(score, board.turn)

        # Extract best move
        best_move = info.get("pv", [None])[0]
        best_move_uci = best_move.uci() if best_move else None
        best_move_san = board.san(best_move) if best_move else None

        return PositionAnalysis(
            eval_centipawns=eval_cp,
            is_mate=is_mate,
            mate_in_n=mate_in_n,
            best_move=best_move_uci,
            best_move_san=best_move_san,
        )

    def analyze_game_positions(
        self,
        boards: list[chess.Board],
        depth: Optional[int] = None,
        progress_callback: Optional[callable] = None,
    ) -> list[PositionAnalysis]:
        """
        Analyze multiple positions (a full game).

        Args:
            boards: List of board positions to analyze
            depth: Analysis depth
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of PositionAnalysis for each position
        """
        results = []
        total = len(boards)

        for i, board in enumerate(boards):
            result = self.analyze_position(board, depth)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, total)

        return results


def calculate_centipawn_loss(
    eval_before: Optional[float],
    eval_after: Optional[float],
    is_mate_before: bool,
    is_mate_after: bool,
    mate_in_n_before: Optional[int],
    mate_in_n_after: Optional[int],
    color: str,
    centipawn_cap: int = 9999,
) -> Optional[float]:
    """
    Calculate centipawn loss for a move.

    For white, positive eval is good, so loss = eval_before - eval_after
    For black, negative eval is good, so loss = eval_after - eval_before

    Mate positions are handled specially:
    - Mate for the player is +cap
    - Mate against the player is -cap
    """
    # Handle mate positions
    if is_mate_before:
        # Convert mate to approximate centipawn value
        if mate_in_n_before is not None:
            if mate_in_n_before > 0:
                # White is mating
                eval_before = centipawn_cap
            else:
                # Black is mating
                eval_before = -centipawn_cap
        else:
            eval_before = 0

    if is_mate_after:
        if mate_in_n_after is not None:
            if mate_in_n_after > 0:
                eval_after = centipawn_cap
            else:
                eval_after = -centipawn_cap
        else:
            eval_after = 0

    if eval_before is None or eval_after is None:
        return None

    # Calculate loss from the perspective of the player who moved
    if color == "white":
        # For white, they want high (positive) eval
        # Loss = how much worse the position got for white
        loss = eval_before - eval_after
    else:
        # For black, they want low (negative) eval
        # Loss = how much worse the position got for black (i.e., how much better for white)
        loss = eval_after - eval_before

    # Centipawn loss should be non-negative (a "gain" is still 0 loss)
    return max(0, loss)
