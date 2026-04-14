"""Analyze command implementation."""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from ..config import Config
from ..database.operations import DatabaseManager
from ..parsing.pgn_parser import parse_pgn
from ..parsing.clock_parser import extract_clock_times, parse_clock_comment
from ..analysis.stockfish import StockfishAnalyzer, calculate_centipawn_loss
from ..analysis.game_phase import detect_phases_for_game


console = Console()


def analyze_single_game(
    game: dict,
    analyzer: StockfishAnalyzer,
    db: DatabaseManager,
    depth: int,
    progress: Progress,
    task_id: int,
) -> bool:
    """
    Analyze a single game and store results.

    Returns True if successful, False otherwise.
    """
    game_id = game["game_id"]
    pgn = game["pgn"]

    # Parse the PGN
    parsed = parse_pgn(pgn)
    if parsed is None:
        console.print(f"[yellow]Failed to parse game {game_id}[/yellow]")
        db.update_game_analysis_status(game_id, "error")
        return False

    if not parsed.moves:
        console.print(f"[yellow]No moves in game {game_id}[/yellow]")
        db.update_game_analysis_status(game_id, "error")
        return False

    # Mark as in progress
    db.update_game_analysis_status(game_id, "in_progress")

    # Get all board positions (including starting position)
    boards_before = [parsed.moves[0].board_before]  # Starting position
    boards_after = [m.board_after for m in parsed.moves]

    # Analyze all positions (before each move, plus final position)
    all_positions = boards_before + boards_after
    total_positions = len(all_positions)

    progress.update(task_id, total=total_positions)

    evaluations = []
    for i, board in enumerate(all_positions):
        eval_result = analyzer.analyze_position(board, depth)
        evaluations.append(eval_result)
        progress.update(task_id, completed=i + 1)

    # Extract clock times
    moves_with_comments = [(m.san, m.comment or "") for m in parsed.moves]
    clock_data = extract_clock_times(
        moves_with_comments,
        game.get("time_control_seconds"),
        game.get("increment_seconds"),
    )

    # Detect game phases
    phases = detect_phases_for_game(boards_after, game.get("eco_code"))

    # Prepare move records
    move_records = []
    for i, move in enumerate(parsed.moves):
        # eval_before is the position before this move (index i)
        # eval_after is the position after this move (index i+1)
        eval_before = evaluations[i]
        eval_after = evaluations[i + 1]

        # Calculate centipawn loss
        cp_loss = calculate_centipawn_loss(
            eval_before.eval_centipawns,
            eval_after.eval_centipawns,
            eval_before.is_mate,
            eval_after.is_mate,
            eval_before.mate_in_n,
            eval_after.mate_in_n,
            move.color,
        )

        # Get clock data
        clock = clock_data[i] if i < len(clock_data) else None

        move_records.append({
            "game_id": game_id,
            "ply_number": move.ply_number,
            "color": move.color,
            "san": move.san,
            "uci": move.uci,
            "clock_time_remaining": clock.clock_time_remaining if clock else None,
            "time_spent": clock.time_spent if clock else None,
            "pct_time_used": clock.pct_time_used if clock else None,
            "eval_before": eval_before.eval_centipawns,
            "eval_after": eval_after.eval_centipawns,
            "centipawn_loss": cp_loss,
            "is_mate_before": int(eval_before.is_mate),
            "is_mate_after": int(eval_after.is_mate),
            "mate_in_n_before": eval_before.mate_in_n,
            "mate_in_n_after": eval_after.mate_in_n,
            "best_move": eval_before.best_move,
            "best_move_san": eval_before.best_move_san,
            "fen": move.board_before.fen(),
            "game_phase": phases[i] if i < len(phases) else "middlegame",
        })

    # Delete any existing moves for this game (in case of re-analysis)
    db.delete_moves_for_game(game_id)

    # Insert moves in batch
    db.insert_moves_batch(move_records)

    # Mark as complete
    db.update_game_analysis_status(game_id, "complete", depth)

    return True


def run_analyze(
    config: Config,
    project_root: Path,
    depth: int = 15,
    limit: Optional[int] = None,
) -> None:
    """Run the analyze command."""
    db_path = config.get_absolute_db_path(project_root)

    if not db_path.exists():
        console.print("[red]Database not found. Run 'chess-insights init' and 'chess-insights fetch' first.[/red]")
        return

    db = DatabaseManager(db_path)

    # Get pending games
    pending_games = db.get_pending_games(limit)

    if not pending_games:
        console.print("[green]No pending games to analyze.[/green]")
        return

    console.print(f"Found {len(pending_games)} games to analyze at depth {depth}")

    # Initialize Stockfish
    analyzer = StockfishAnalyzer(config.stockfish)

    games_analyzed = 0
    games_failed = 0

    try:
        with analyzer.session():
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                overall_task = progress.add_task(
                    f"Analyzing {len(pending_games)} games...",
                    total=len(pending_games)
                )

                for i, game in enumerate(pending_games):
                    game_task = progress.add_task(
                        f"Game {i + 1}: {game.get('white_username', 'White')} vs {game.get('black_username', 'Black')}",
                        total=100
                    )

                    try:
                        success = analyze_single_game(
                            game, analyzer, db, depth, progress, game_task
                        )
                        if success:
                            games_analyzed += 1
                        else:
                            games_failed += 1
                    except Exception as e:
                        console.print(f"[red]Error analyzing game {game['game_id']}: {e}[/red]")
                        db.update_game_analysis_status(game["game_id"], "error")
                        games_failed += 1

                    progress.remove_task(game_task)
                    progress.update(overall_task, completed=i + 1)

    except FileNotFoundError:
        console.print(f"[red]Stockfish not found at {config.stockfish.path}[/red]")
        console.print("Please update the path in config.yaml or set the STOCKFISH_PATH environment variable.")
        return
    except Exception as e:
        console.print(f"[red]Error initializing Stockfish: {e}[/red]")
        return

    console.print(f"\n[green]Analysis complete![/green]")
    console.print(f"  Games analyzed: {games_analyzed}")
    console.print(f"  Games failed: {games_failed}")
