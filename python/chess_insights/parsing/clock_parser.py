"""Clock time extraction from PGN moves."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClockData:
    """Clock time data for a single move."""
    clock_time_remaining: Optional[float]  # Seconds remaining after move
    time_spent: Optional[float]  # Seconds spent on this move
    pct_time_used: Optional[float]  # Cumulative percentage of initial time used


def parse_clock_comment(comment: str) -> Optional[float]:
    """
    Parse clock time from a PGN comment.

    Clock comments look like: [%clk 0:05:23.4] or [%clk 1:30:00]

    Returns time in seconds.
    """
    match = re.search(r'\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]', comment)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    return None


def extract_clock_times(
    moves_with_comments: list[tuple[str, str]],
    initial_time_seconds: Optional[int],
    increment_seconds: Optional[int] = 0,
) -> list[ClockData]:
    """
    Extract clock data for a list of moves.

    Args:
        moves_with_comments: List of (move_san, comment) tuples
        initial_time_seconds: Initial time in seconds
        increment_seconds: Increment per move in seconds

    Returns:
        List of ClockData for each move
    """
    results = []
    prev_white_time = initial_time_seconds
    prev_black_time = initial_time_seconds
    total_white_time_used = 0.0
    total_black_time_used = 0.0

    for i, (_, comment) in enumerate(moves_with_comments):
        is_white = (i % 2 == 0)
        clock_remaining = parse_clock_comment(comment) if comment else None

        time_spent = None
        pct_time_used = None

        if clock_remaining is not None:
            if is_white and prev_white_time is not None:
                # Time spent = previous remaining + increment - current remaining
                time_spent = prev_white_time + (increment_seconds or 0) - clock_remaining
                time_spent = max(0, time_spent)  # Can't be negative
                total_white_time_used += time_spent
                if initial_time_seconds and initial_time_seconds > 0:
                    pct_time_used = total_white_time_used / initial_time_seconds * 100
                prev_white_time = clock_remaining
            elif not is_white and prev_black_time is not None:
                time_spent = prev_black_time + (increment_seconds or 0) - clock_remaining
                time_spent = max(0, time_spent)
                total_black_time_used += time_spent
                if initial_time_seconds and initial_time_seconds > 0:
                    pct_time_used = total_black_time_used / initial_time_seconds * 100
                prev_black_time = clock_remaining

        results.append(ClockData(
            clock_time_remaining=clock_remaining,
            time_spent=time_spent,
            pct_time_used=pct_time_used,
        ))

    return results
