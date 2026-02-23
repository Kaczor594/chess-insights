"""Game phase detection (opening, middlegame, endgame)."""

import chess


# Piece values for material calculation
PIECE_VALUES = {
    chess.QUEEN: 9,
    chess.ROOK: 5,
    chess.BISHOP: 3,
    chess.KNIGHT: 3,
    chess.PAWN: 1,
}

# Endgame threshold: total material (excluding kings) <= 13
ENDGAME_MATERIAL_THRESHOLD = 13

# Opening ends by this ply at the latest (move 10 = ply 20)
MAX_OPENING_PLY = 20


def calculate_total_material(board: chess.Board) -> int:
    """
    Calculate total material on the board (excluding kings).

    Uses standard piece values: Q=9, R=5, B=3, N=3, P=1

    Returns:
        Total material value for both sides combined
    """
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        # Count pieces of this type for both colors
        white_count = len(board.pieces(piece_type, chess.WHITE))
        black_count = len(board.pieces(piece_type, chess.BLACK))
        total += (white_count + black_count) * value
    return total


def has_major_exchange_happened(board_before: chess.Board, board_after: chess.Board) -> bool:
    """
    Check if a major piece exchange (or capture) happened.

    A "major exchange" is defined as capturing a piece worth >= 3 points
    (i.e., not just a pawn).
    """
    material_before = calculate_total_material(board_before)
    material_after = calculate_total_material(board_after)

    # If material dropped by 3+ points, a significant capture occurred
    return (material_before - material_after) >= 3


def detect_game_phase(
    board: chess.Board,
    ply_number: int,
    opening_line_ended: bool = False,
) -> str:
    """
    Detect the game phase for a position.

    Rules:
    - Opening: Until ECO opening line ends OR ply <= 20 with no major exchanges
    - Endgame: Total material (excluding kings) <= 13 points
    - Middlegame: Everything between

    Args:
        board: The chess position after the move
        ply_number: The ply number (0-indexed)
        opening_line_ended: Whether we've exited the ECO opening line

    Returns:
        "opening", "middlegame", or "endgame"
    """
    total_material = calculate_total_material(board)

    # Check for endgame first (material threshold)
    if total_material <= ENDGAME_MATERIAL_THRESHOLD:
        return "endgame"

    # Check for opening
    if not opening_line_ended and ply_number < MAX_OPENING_PLY:
        return "opening"

    # Default to middlegame
    return "middlegame"


def detect_phases_for_game(
    boards: list[chess.Board],
    eco_code: str | None = None,
) -> list[str]:
    """
    Detect game phases for all positions in a game.

    Args:
        boards: List of board positions (after each move)
        eco_code: ECO code for the opening (if available)

    Returns:
        List of phase strings for each position
    """
    phases = []
    opening_ended = False

    for ply, board in enumerate(boards):
        if not opening_ended:
            # Check if we should end the opening
            # For simplicity, we end opening after move 10 or when material drops significantly
            if ply >= MAX_OPENING_PLY:
                opening_ended = True
            elif ply > 0 and ply < len(boards):
                # Check for significant material change (captures)
                prev_material = calculate_total_material(boards[ply - 1] if ply > 0 else board)
                curr_material = calculate_total_material(board)
                if prev_material - curr_material >= 6:  # Major exchange
                    opening_ended = True

        phase = detect_game_phase(board, ply, opening_ended)
        phases.append(phase)

        # Once we hit endgame, stay in endgame
        if phase == "endgame":
            opening_ended = True

    return phases
