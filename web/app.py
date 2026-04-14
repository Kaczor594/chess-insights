"""Flask app for the Chess Puzzle Trainer."""

import atexit
import math
import sqlite3
from pathlib import Path

import chess
import chess.engine
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "chess_insights.db"
STOCKFISH_PATH = "/Users/isaackaczor/Downloads/stockfish/stockfish-macos-m1-apple-silicon"
ANALYSIS_DEPTH = 15

COEFF = 250 / math.log(6)
PLAYER_USERNAME = "kaczor594"

engine: chess.engine.SimpleEngine = None


def get_db():
    """Get a database connection for the current request, reusing if possible."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close database connection at the end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def puzzle_threshold(eval_cp: float) -> float:
    """Dynamic centipawn-loss threshold for puzzle eligibility.

    y = (250 / ln(6)) * ln(|x| + 1) + 50
    where x = eval_before in pawns (eval_cp / 100).
    """
    x = eval_cp / 100
    return COEFF * math.log(abs(x) + 1) + 50


# SQL fragment for the dynamic threshold (mirrors puzzle_threshold in SQL)
THRESHOLD_SQL = "(250.0 / ln(6)) * ln(abs(m.eval_before / 100.0) + 1) + 50"

# Base WHERE clause for eligible puzzles (shared between count and selection)
ELIGIBLE_WHERE = f"""
    m.centipawn_loss IS NOT NULL
    AND m.eval_before IS NOT NULL
    AND m.best_move_san IS NOT NULL
    AND m.best_move IS NOT NULL
    AND m.fen IS NOT NULL
    AND m.best_move_san NOT LIKE '?%%'
    AND m.puzzle_solved = 0
    AND (
        (g.white_player_id = :player_id AND m.color = 'white')
        OR (g.black_player_id = :player_id AND m.color = 'black')
    )
    AND NOT (m.mate_in_n_before IS NOT NULL AND (
        (m.color = 'white' AND m.mate_in_n_before < 0)
        OR (m.color = 'black' AND m.mate_in_n_before > 0)
    ))
    AND m.centipawn_loss >= {THRESHOLD_SQL}
"""


def _get_player_id(conn) -> int | None:
    """Look up the player_id for PLAYER_USERNAME."""
    c = conn.execute(
        "SELECT player_id FROM players WHERE username = ?", (PLAYER_USERNAME,)
    )
    row = c.fetchone()
    return row["player_id"] if row else None


def get_random_puzzle_id(conn) -> int | None:
    """Pick a random eligible puzzle move_id directly from the database."""
    player_id = _get_player_id(conn)
    if player_id is None:
        return None

    row = conn.execute(
        f"""
        SELECT m.move_id
        FROM moves m
        JOIN games g ON m.game_id = g.game_id
        WHERE {ELIGIBLE_WHERE}
        ORDER BY RANDOM() LIMIT 1
        """,
        {"player_id": player_id},
    ).fetchone()

    return row["move_id"] if row else None


def get_eligible_count(conn) -> int:
    """Count the number of remaining eligible puzzles."""
    player_id = _get_player_id(conn)
    if player_id is None:
        return 0

    row = conn.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM moves m
        JOIN games g ON m.game_id = g.game_id
        WHERE {ELIGIBLE_WHERE}
        """,
        {"player_id": player_id},
    ).fetchone()

    return row["cnt"]


def get_puzzle_data(move_id: int):
    """Full puzzle data for display (used by the random/specific puzzle endpoints)."""
    conn = get_db()
    row = conn.execute(
        """
        SELECT m.move_id, m.fen, m.color, m.san, m.best_move, m.best_move_san,
               m.centipawn_loss, m.eval_before, m.game_phase, m.ply_number,
               g.date_played, g.time_control, g.url AS game_url,
               pw.username AS white_username, pb.username AS black_username
        FROM moves m
        JOIN games g ON m.game_id = g.game_id
        JOIN players pw ON g.white_player_id = pw.player_id
        JOIN players pb ON g.black_player_id = pb.player_id
        WHERE m.move_id = ?
        """,
        (move_id,),
    ).fetchone()

    if not row:
        return None

    if row["white_username"] == PLAYER_USERNAME:
        player_color = "white"
        opponent = row["black_username"]
    else:
        player_color = "black"
        opponent = row["white_username"]

    move_number = (row["ply_number"] // 2) + 1

    return {
        "move_id": row["move_id"],
        "fen": row["fen"],
        "player_color": player_color,
        "best_move_uci": row["best_move"],
        "best_move_san": row["best_move_san"],
        "actual_move_san": row["san"],
        "actual_cp_loss": row["centipawn_loss"],
        "eval_before": row["eval_before"],
        "game_phase": row["game_phase"],
        "move_number": move_number,
        "opponent": opponent,
        "date_played": row["date_played"],
        "game_url": row["game_url"],
        "time_control": row["time_control"],
    }


def get_eval_context(move_id: int):
    """Lightweight query for the evaluate endpoint — only the fields needed for grading."""
    conn = get_db()
    row = conn.execute(
        """
        SELECT m.color, m.san, m.best_move, m.best_move_san,
               m.centipawn_loss, m.eval_before,
               pw.username AS white_username
        FROM moves m
        JOIN games g ON m.game_id = g.game_id
        JOIN players pw ON g.white_player_id = pw.player_id
        WHERE m.move_id = ?
        """,
        (move_id,),
    ).fetchone()

    if not row:
        return None

    player_color = "white" if row["white_username"] == PLAYER_USERNAME else "black"

    return {
        "player_color": player_color,
        "best_move_uci": row["best_move"],
        "best_move_san": row["best_move_san"],
        "actual_move_san": row["san"],
        "actual_cp_loss": row["centipawn_loss"],
        "eval_before": row["eval_before"],
    }


def eval_score_to_cp(score: chess.engine.PovScore, player_color: str) -> float:
    """Convert a PovScore to centipawns from the player's perspective."""
    white_score = score.white()
    if white_score.is_mate():
        mate_in = white_score.mate()
        cp = 10000 if mate_in > 0 else -10000
    else:
        cp = white_score.score()

    if player_color == "black":
        cp = -cp

    return cp


# --- Routes ---


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/puzzle/random")
def random_puzzle():
    conn = get_db()
    move_id = get_random_puzzle_id(conn)
    if move_id is None:
        return jsonify({"error": "No puzzles available"}), 404

    data = get_puzzle_data(move_id)
    if not data:
        return jsonify({"error": "Puzzle not found"}), 404
    return jsonify(data)


@app.route("/api/puzzle/<int:move_id>")
def get_puzzle(move_id):
    data = get_puzzle_data(move_id)
    if not data:
        return jsonify({"error": "Puzzle not found"}), 404
    return jsonify(data)


@app.route("/api/evaluate", methods=["POST"])
def evaluate_move():
    """Evaluate the user's move with Stockfish and grade it."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    fen = data.get("fen")
    user_uci = data.get("user_move_uci")
    move_id = data.get("move_id")

    if not all([fen, user_uci, move_id]):
        return jsonify({"error": "Missing fen, user_move_uci, or move_id"}), 400

    puzzle = get_eval_context(move_id)
    if not puzzle:
        return jsonify({"error": "Puzzle not found"}), 404

    player_color = puzzle["player_color"]
    eval_before = puzzle["eval_before"]
    threshold = puzzle_threshold(eval_before)

    is_best = user_uci == puzzle["best_move_uci"]

    board = chess.Board(fen)
    try:
        user_move = chess.Move.from_uci(user_uci)
        user_san = board.san(user_move)
        board.push(user_move)
    except (ValueError, chess.InvalidMoveError):
        return jsonify({"error": "Invalid move"}), 400

    info = engine.analyse(board, chess.engine.Limit(depth=ANALYSIS_DEPTH))
    user_eval_cp = eval_score_to_cp(info["score"], player_color)

    if player_color == "white":
        eval_before_player = eval_before
    else:
        eval_before_player = -eval_before

    user_cp_loss = max(0, eval_before_player - user_eval_cp)

    if is_best:
        result = "perfect"
    elif user_cp_loss < threshold:
        result = "pass"
    else:
        result = "fail"

    # Mark puzzle as solved on pass or perfect
    conn = get_db()
    if result in ("perfect", "pass"):
        conn.execute(
            "UPDATE moves SET puzzle_solved = 1 WHERE move_id = ?", (move_id,)
        )
        conn.commit()

    remaining = get_eligible_count(conn)

    return jsonify({
        "result": result,
        "user_move_san": user_san,
        "user_cp_loss": round(user_cp_loss, 1),
        "user_eval": round(user_eval_cp, 1),
        "best_move_san": puzzle["best_move_san"],
        "best_move_uci": puzzle["best_move_uci"],
        "actual_move_san": puzzle["actual_move_san"],
        "actual_cp_loss": round(puzzle["actual_cp_loss"], 1),
        "eval_before": eval_before,
        "threshold": round(threshold, 1),
        "remaining_puzzles": remaining,
    })


@app.route("/api/stats")
def puzzle_stats():
    conn = get_db()
    return jsonify({
        "remaining_puzzles": get_eligible_count(conn),
    })


if __name__ == "__main__":
    # Quick startup check: print eligible count
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.execute("SELECT player_id FROM players WHERE username = ?", (PLAYER_USERNAME,))
    row = c.fetchone()
    if row:
        player_id = row["player_id"]
        cnt = conn.execute(
            f"""
            SELECT COUNT(*) AS cnt
            FROM moves m
            JOIN games g ON m.game_id = g.game_id
            WHERE {ELIGIBLE_WHERE}
            """,
            {"player_id": player_id},
        ).fetchone()["cnt"]
        print(f"{cnt} eligible puzzles")
    conn.close()

    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({"Threads": 4, "Hash": 256})
    print("Stockfish engine ready")

    atexit.register(engine.quit)

    app.run(debug=True, port=8000, use_reloader=False)
