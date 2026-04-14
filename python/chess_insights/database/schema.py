"""Database schema definitions for chess-insights."""

SCHEMA_SQL = """
-- Players table
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('chesscom', 'lichess')),
    UNIQUE(username, platform)
);

-- Games table
CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL CHECK (platform IN ('chesscom', 'lichess')),
    platform_game_id TEXT NOT NULL,
    white_player_id INTEGER NOT NULL REFERENCES players(player_id),
    black_player_id INTEGER NOT NULL REFERENCES players(player_id),
    white_rating INTEGER,
    black_rating INTEGER,
    time_control TEXT,
    time_control_seconds INTEGER,
    increment_seconds INTEGER,
    date_played TEXT,
    result TEXT CHECK (result IN ('1-0', '0-1', '1/2-1/2', '*')),
    termination_reason TEXT,
    eco_code TEXT,
    opening_name TEXT,
    url TEXT,
    pgn TEXT NOT NULL,
    analysis_status TEXT NOT NULL DEFAULT 'pending' CHECK (analysis_status IN ('pending', 'in_progress', 'complete', 'error')),
    analysis_depth INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(platform, platform_game_id)
);

-- Moves table
CREATE TABLE IF NOT EXISTS moves (
    move_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    ply_number INTEGER NOT NULL,
    color TEXT NOT NULL CHECK (color IN ('white', 'black')),
    san TEXT NOT NULL,
    uci TEXT,
    clock_time_remaining REAL,
    time_spent REAL,
    pct_time_used REAL,
    eval_before REAL,
    eval_after REAL,
    centipawn_loss REAL,
    is_mate_before INTEGER DEFAULT 0,
    is_mate_after INTEGER DEFAULT 0,
    mate_in_n_before INTEGER,
    mate_in_n_after INTEGER,
    best_move TEXT,
    best_move_san TEXT,
    fen TEXT,
    puzzle_solved INTEGER DEFAULT 0,
    game_phase TEXT CHECK (game_phase IN ('opening', 'middlegame', 'endgame')),
    UNIQUE(game_id, ply_number)
);

-- Sync metadata table for incremental syncing
CREATE TABLE IF NOT EXISTS sync_metadata (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('chesscom', 'lichess')),
    last_sync_timestamp TEXT,
    last_game_timestamp TEXT,
    games_fetched INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(username, platform)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_games_platform ON games(platform);
CREATE INDEX IF NOT EXISTS idx_games_analysis_status ON games(analysis_status);
CREATE INDEX IF NOT EXISTS idx_games_date_played ON games(date_played);
CREATE INDEX IF NOT EXISTS idx_games_white_player ON games(white_player_id);
CREATE INDEX IF NOT EXISTS idx_games_black_player ON games(black_player_id);
CREATE INDEX IF NOT EXISTS idx_moves_game_id ON moves(game_id);
CREATE INDEX IF NOT EXISTS idx_moves_game_phase ON moves(game_phase);
CREATE INDEX IF NOT EXISTS idx_moves_puzzle_eligible ON moves(puzzle_solved, centipawn_loss, eval_before);
CREATE INDEX IF NOT EXISTS idx_players_username_platform ON players(username, platform);

-- Trigger to update updated_at on games
CREATE TRIGGER IF NOT EXISTS update_games_timestamp
AFTER UPDATE ON games
BEGIN
    UPDATE games SET updated_at = datetime('now') WHERE game_id = NEW.game_id;
END;

-- Trigger to update updated_at on sync_metadata
CREATE TRIGGER IF NOT EXISTS update_sync_metadata_timestamp
AFTER UPDATE ON sync_metadata
BEGIN
    UPDATE sync_metadata SET updated_at = datetime('now') WHERE sync_id = NEW.sync_id;
END;
"""


def get_schema() -> str:
    """Return the database schema SQL."""
    return SCHEMA_SQL
