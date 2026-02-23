"""Fetch command implementation."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import Config
from ..database.operations import DatabaseManager
from ..api.base import ChessApiClient, GameData
from ..api.chesscom import ChesscomClient


console = Console()


def get_api_client(platform: str, config: Config) -> ChessApiClient:
    """Get the appropriate API client for a platform."""
    if platform == "chesscom":
        return ChesscomClient(
            user_agent=config.api.user_agent,
            delay=config.api.chesscom_delay,
        )
    elif platform == "lichess":
        # Import here to avoid circular imports
        from ..api.lichess import LichessClient
        return LichessClient(
            user_agent=config.api.user_agent,
            delay=config.api.lichess_delay,
        )
    else:
        raise ValueError(f"Unknown platform: {platform}")


def store_game(db: DatabaseManager, game: GameData) -> Optional[int]:
    """Store a game in the database. Returns game_id if stored, None if skipped."""
    # Check if game already exists
    if db.game_exists(game.platform, game.platform_game_id):
        return None

    # Get or create players
    white_player_id = db.get_or_create_player(game.white_username, game.platform)
    black_player_id = db.get_or_create_player(game.black_username, game.platform)

    # Insert the game
    game_id = db.insert_game(
        platform=game.platform,
        platform_game_id=game.platform_game_id,
        white_player_id=white_player_id,
        black_player_id=black_player_id,
        white_rating=game.white_rating,
        black_rating=game.black_rating,
        time_control=game.time_control,
        time_control_seconds=game.time_control_seconds,
        increment_seconds=game.increment_seconds,
        date_played=game.date_played,
        result=game.result,
        termination_reason=game.termination_reason,
        eco_code=game.eco_code,
        opening_name=game.opening_name,
        url=game.url,
        pgn=game.pgn,
    )

    return game_id


def run_fetch(
    config: Config,
    project_root: Path,
    username: str,
    platform: str,
    full_refresh: bool = False,
) -> None:
    """Run the fetch command."""
    db_path = config.get_absolute_db_path(project_root)

    if not db_path.exists():
        console.print("[yellow]Database not found. Initializing...[/yellow]")
        db = DatabaseManager(db_path)
        db.initialize()
    else:
        db = DatabaseManager(db_path)

    # Get API client
    try:
        client = get_api_client(platform, config)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    # Check for existing sync metadata
    since_timestamp = None
    if not full_refresh:
        sync_meta = db.get_sync_metadata(username, platform)
        if sync_meta and sync_meta.get("last_game_timestamp"):
            since_timestamp = sync_meta["last_game_timestamp"]
            console.print(f"[dim]Fetching games since {since_timestamp}[/dim]")

    # Fetch games
    games_stored = 0
    games_skipped = 0
    latest_timestamp = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Fetching games for {username}...", total=None)

        try:
            for game in client.fetch_games(username, since_timestamp):
                game_id = store_game(db, game)
                if game_id:
                    games_stored += 1
                    progress.update(task, description=f"Stored {games_stored} games...")

                    # Track latest timestamp
                    if game.date_played:
                        if latest_timestamp is None or game.date_played > latest_timestamp:
                            latest_timestamp = game.date_played
                else:
                    games_skipped += 1

        except Exception as e:
            console.print(f"[red]Error fetching games: {e}[/red]")
            return

    # Update sync metadata
    db.upsert_sync_metadata(
        username=username,
        platform=platform,
        last_sync_timestamp=datetime.utcnow().isoformat(),
        last_game_timestamp=latest_timestamp,
        games_fetched=games_stored,
    )

    console.print(f"[green]Fetch complete![/green]")
    console.print(f"  Games stored: {games_stored}")
    console.print(f"  Games skipped (already exist): {games_skipped}")
