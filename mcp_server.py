#!/usr/bin/env python3
"""
Chess Insights MCP Server

Local MCP server for querying the chess insights database.
Provides tools to analyze games, moves, and player performance.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Any, Sequence

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server

# Database path
DB_PATH = Path(__file__).parent / "data" / "chess_insights.db"

# Initialize MCP server
app = Server("chess-insights")

# Security settings
MAX_ROWS = 500


def get_connection() -> sqlite3.Connection:
    """Get a read-only database connection."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def execute_query(query: str, params: tuple = ()) -> dict:
    """Execute a read-only query safely."""
    # Validate query is read-only
    query_upper = query.strip().upper()
    if not query_upper.startswith(('SELECT', 'WITH', 'PRAGMA')):
        return {"success": False, "error": "Only SELECT queries allowed"}

    forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE']
    for keyword in forbidden:
        if keyword in query_upper:
            return {"success": False, "error": f"Forbidden keyword: {keyword}"}

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchmany(MAX_ROWS + 1)

        truncated = len(rows) > MAX_ROWS
        if truncated:
            rows = rows[:MAX_ROWS]

        results = [dict(row) for row in rows]
        conn.close()

        return {
            "success": True,
            "data": results,
            "row_count": len(results),
            "truncated": truncated
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="list_tables",
            description="List all tables in the chess database",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="describe_table",
            description="Get column information for a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name: players, games, moves, or sync_metadata"
                    }
                },
                "required": ["table"]
            }
        ),
        Tool(
            name="get_player_stats",
            description="Get statistics for a player by username",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Player username"
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["chesscom", "lichess"],
                        "description": "Chess platform (chesscom or lichess)"
                    }
                },
                "required": ["username"]
            }
        ),
        Tool(
            name="get_recent_games",
            description="Get recent games for a player",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Player username"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of games to return (default: 10)"
                    }
                },
                "required": ["username"]
            }
        ),
        Tool(
            name="get_game_moves",
            description="Get all moves for a specific game",
            inputSchema={
                "type": "object",
                "properties": {
                    "game_id": {
                        "type": "number",
                        "description": "Game ID from the games table"
                    }
                },
                "required": ["game_id"]
            }
        ),
        Tool(
            name="get_opening_stats",
            description="Get statistics for openings played",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Player username (optional - all players if omitted)"
                    },
                    "color": {
                        "type": "string",
                        "enum": ["white", "black"],
                        "description": "Filter by color played (optional)"
                    }
                }
            }
        ),
        Tool(
            name="get_time_analysis",
            description="Analyze time usage patterns in games",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Player username"
                    },
                    "game_id": {
                        "type": "number",
                        "description": "Specific game ID (optional)"
                    }
                }
            }
        ),
        Tool(
            name="get_accuracy_stats",
            description="Get move accuracy and centipawn loss statistics",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Player username"
                    },
                    "game_phase": {
                        "type": "string",
                        "enum": ["opening", "middlegame", "endgame"],
                        "description": "Filter by game phase (optional)"
                    }
                }
            }
        ),
        Tool(
            name="execute_query",
            description="Execute a custom read-only SQL query for advanced analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL SELECT query to execute"
                    }
                },
                "required": ["query"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool execution."""

    try:
        if name == "list_tables":
            query = "SELECT name, type FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            result = execute_query(query)

        elif name == "describe_table":
            table = arguments.get("table", "")
            if table not in ["players", "games", "moves", "sync_metadata"]:
                result = {"success": False, "error": f"Unknown table: {table}"}
            else:
                query = f'PRAGMA table_info("{table}")'
                result = execute_query(query)

                # Also get row count
                count_result = execute_query(f'SELECT COUNT(*) as count FROM "{table}"')
                if count_result["success"] and count_result["data"]:
                    result["row_count_total"] = count_result["data"][0]["count"]

        elif name == "get_player_stats":
            username = arguments.get("username", "")
            platform = arguments.get("platform")

            platform_filter = f"AND p.platform = '{platform}'" if platform else ""

            query = f"""
                SELECT
                    p.username,
                    p.platform,
                    COUNT(DISTINCT g.game_id) as total_games,
                    SUM(CASE WHEN (g.white_player_id = p.player_id AND g.result = '1-0')
                             OR (g.black_player_id = p.player_id AND g.result = '0-1') THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN g.result = '1/2-1/2' THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN (g.white_player_id = p.player_id AND g.result = '0-1')
                             OR (g.black_player_id = p.player_id AND g.result = '1-0') THEN 1 ELSE 0 END) as losses,
                    ROUND(AVG(CASE WHEN g.white_player_id = p.player_id THEN g.white_rating ELSE g.black_rating END), 0) as avg_rating,
                    MAX(CASE WHEN g.white_player_id = p.player_id THEN g.white_rating ELSE g.black_rating END) as max_rating
                FROM players p
                LEFT JOIN games g ON p.player_id = g.white_player_id OR p.player_id = g.black_player_id
                WHERE LOWER(p.username) = LOWER(?)
                {platform_filter}
                GROUP BY p.player_id
            """
            result = execute_query(query, (username,))

        elif name == "get_recent_games":
            username = arguments.get("username", "")
            limit = min(arguments.get("limit", 10), 50)

            query = """
                SELECT
                    g.game_id,
                    g.date_played,
                    g.time_control,
                    pw.username as white_player,
                    g.white_rating,
                    pb.username as black_player,
                    g.black_rating,
                    g.result,
                    g.opening_name,
                    g.eco_code,
                    g.termination_reason
                FROM games g
                JOIN players pw ON g.white_player_id = pw.player_id
                JOIN players pb ON g.black_player_id = pb.player_id
                WHERE LOWER(pw.username) = LOWER(?) OR LOWER(pb.username) = LOWER(?)
                ORDER BY g.date_played DESC
                LIMIT ?
            """
            result = execute_query(query, (username, username, limit))

        elif name == "get_game_moves":
            game_id = arguments.get("game_id")

            query = """
                SELECT
                    m.ply_number,
                    m.color,
                    m.san,
                    m.time_spent,
                    m.clock_time_remaining,
                    m.eval_before,
                    m.eval_after,
                    m.centipawn_loss,
                    m.best_move,
                    m.game_phase
                FROM moves m
                WHERE m.game_id = ?
                ORDER BY m.ply_number
            """
            result = execute_query(query, (game_id,))

        elif name == "get_opening_stats":
            username = arguments.get("username")
            color = arguments.get("color")

            where_clauses = []
            params = []

            if username:
                where_clauses.append("(LOWER(pw.username) = LOWER(?) OR LOWER(pb.username) = LOWER(?))")
                params.extend([username, username])

            if color == "white" and username:
                where_clauses.append("LOWER(pw.username) = LOWER(?)")
                params.append(username)
            elif color == "black" and username:
                where_clauses.append("LOWER(pb.username) = LOWER(?)")
                params.append(username)

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            query = f"""
                SELECT
                    g.eco_code,
                    g.opening_name,
                    COUNT(*) as games_played,
                    SUM(CASE WHEN g.result = '1-0' THEN 1 ELSE 0 END) as white_wins,
                    SUM(CASE WHEN g.result = '0-1' THEN 1 ELSE 0 END) as black_wins,
                    SUM(CASE WHEN g.result = '1/2-1/2' THEN 1 ELSE 0 END) as draws
                FROM games g
                JOIN players pw ON g.white_player_id = pw.player_id
                JOIN players pb ON g.black_player_id = pb.player_id
                {where_sql}
                GROUP BY g.eco_code, g.opening_name
                ORDER BY games_played DESC
                LIMIT 20
            """
            result = execute_query(query, tuple(params))

        elif name == "get_time_analysis":
            username = arguments.get("username")
            game_id = arguments.get("game_id")

            if game_id:
                query = """
                    SELECT
                        m.ply_number,
                        m.color,
                        m.san,
                        m.time_spent,
                        m.clock_time_remaining,
                        m.pct_time_used,
                        m.game_phase
                    FROM moves m
                    WHERE m.game_id = ? AND m.time_spent IS NOT NULL
                    ORDER BY m.ply_number
                """
                result = execute_query(query, (game_id,))
            elif username:
                query = """
                    SELECT
                        m.game_phase,
                        m.color,
                        AVG(m.time_spent) as avg_time_spent,
                        MAX(m.time_spent) as max_time_spent,
                        AVG(m.pct_time_used) as avg_pct_time_used,
                        COUNT(*) as total_moves
                    FROM moves m
                    JOIN games g ON m.game_id = g.game_id
                    JOIN players p ON (g.white_player_id = p.player_id AND m.color = 'white')
                                   OR (g.black_player_id = p.player_id AND m.color = 'black')
                    WHERE LOWER(p.username) = LOWER(?) AND m.time_spent IS NOT NULL
                    GROUP BY m.game_phase, m.color
                """
                result = execute_query(query, (username,))
            else:
                result = {"success": False, "error": "Provide username or game_id"}

        elif name == "get_accuracy_stats":
            username = arguments.get("username", "")
            game_phase = arguments.get("game_phase")

            phase_filter = f"AND m.game_phase = '{game_phase}'" if game_phase else ""

            query = f"""
                SELECT
                    m.game_phase,
                    COUNT(*) as total_moves,
                    AVG(m.centipawn_loss) as avg_centipawn_loss,
                    MAX(m.centipawn_loss) as max_centipawn_loss,
                    SUM(CASE WHEN m.centipawn_loss = 0 THEN 1 ELSE 0 END) as perfect_moves,
                    SUM(CASE WHEN m.centipawn_loss > 100 THEN 1 ELSE 0 END) as blunders
                FROM moves m
                JOIN games g ON m.game_id = g.game_id
                JOIN players p ON (g.white_player_id = p.player_id AND m.color = 'white')
                               OR (g.black_player_id = p.player_id AND m.color = 'black')
                WHERE LOWER(p.username) = LOWER(?)
                AND m.centipawn_loss IS NOT NULL
                {phase_filter}
                GROUP BY m.game_phase
            """
            result = execute_query(query, (username,))

        elif name == "execute_query":
            query = arguments.get("query", "")
            result = execute_query(query)

        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str)
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"success": False, "error": str(e)})
        )]


async def main():
    """Run the MCP server."""
    print(f"Chess Insights MCP Server starting...", file=__import__('sys').stderr)
    print(f"Database: {DB_PATH}", file=__import__('sys').stderr)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
