"""CLI definitions for chess-insights."""

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import Config
from .database.operations import DatabaseManager
from .commands.fetch import run_fetch
from .commands.analyze import run_analyze


console = Console()


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="chess-insights",
        description="Chess game analysis tool",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to config.yaml file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    subparsers.add_parser("init", help="Initialize the database")

    # fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch games from a chess platform")
    fetch_parser.add_argument("username", help="Username to fetch games for")
    fetch_parser.add_argument(
        "--platform", "-p",
        choices=["chesscom", "lichess"],
        default="chesscom",
        help="Platform to fetch from (default: chesscom)",
    )
    fetch_parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Fetch all games, ignoring previous sync state",
    )

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze pending games with Stockfish")
    analyze_parser.add_argument(
        "--depth", "-d",
        type=int,
        choices=[15, 18, 20, 25],
        default=15,
        help="Analysis depth (default: 15)",
    )
    analyze_parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Maximum number of games to analyze",
    )

    # status command
    subparsers.add_parser("status", help="Show database statistics")

    return parser


def cmd_init(config: Config, project_root: Path) -> None:
    """Initialize the database."""
    db_path = config.get_absolute_db_path(project_root)
    db = DatabaseManager(db_path)
    db.initialize()
    console.print(f"[green]Database initialized at {db_path}[/green]")


def cmd_status(config: Config, project_root: Path) -> None:
    """Show database statistics."""
    db_path = config.get_absolute_db_path(project_root)
    if not db_path.exists():
        console.print("[yellow]Database not found. Run 'chess-insights init' first.[/yellow]")
        return

    db = DatabaseManager(db_path)
    stats = db.get_statistics()

    table = Table(title="Chess Insights Database Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Games", str(stats["total_games"]))
    table.add_row("Total Moves", str(stats["total_moves"]))
    table.add_row("Total Players", str(stats["total_players"]))

    for status, count in stats.get("by_status", {}).items():
        table.add_row(f"Games ({status})", str(count))

    for platform, count in stats.get("by_platform", {}).items():
        table.add_row(f"Games ({platform})", str(count))

    console.print(table)


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    project_root = get_project_root()
    config = Config.load(args.config)

    if args.command == "init":
        cmd_init(config, project_root)
    elif args.command == "fetch":
        run_fetch(
            config=config,
            project_root=project_root,
            username=args.username,
            platform=args.platform,
            full_refresh=args.full_refresh,
        )
    elif args.command == "analyze":
        run_analyze(
            config=config,
            project_root=project_root,
            depth=args.depth,
            limit=args.limit,
        )
    elif args.command == "status":
        cmd_status(config, project_root)
