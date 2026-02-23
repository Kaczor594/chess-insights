# Chess Insights - Data Loading
# Functions for loading data from SQLite database

source(here::here("R", "scripts", "00_setup.R"))

#' Connect to the chess insights database
#' @return DBI connection object
connect_db <- function(db_path = config$db_path) {
  if (!file.exists(db_path)) {
    stop(glue("Database not found at {db_path}. Run 'chess-insights init' and 'chess-insights fetch' first."))
  }
  dbConnect(RSQLite::SQLite(), db_path)
}

#' Disconnect from database
#' @param con DBI connection object
disconnect_db <- function(con) {
  dbDisconnect(con)
}

#' Load all games with player info
#' @param con DBI connection
#' @return tibble of games
load_games <- function(con) {
  query <- "
    SELECT
      g.*,
      pw.username as white_username,
      pb.username as black_username
    FROM games g
    JOIN players pw ON g.white_player_id = pw.player_id
    JOIN players pb ON g.black_player_id = pb.player_id
    ORDER BY g.date_played DESC
  "
  dbGetQuery(con, query) %>%
    as_tibble() %>%
    mutate(
      date_played = ymd_hms(date_played),
      created_at = ymd_hms(created_at),
      updated_at = ymd_hms(updated_at)
    )
}

#' Load all moves
#' @param con DBI connection
#' @return tibble of moves
load_moves <- function(con) {
  query <- "SELECT * FROM moves ORDER BY game_id, ply_number"
  dbGetQuery(con, query) %>%
    as_tibble() %>%
    mutate(
      color = factor(color, levels = c("white", "black")),
      game_phase = factor(game_phase, levels = c("opening", "middlegame", "endgame"))
    )
}

#' Load moves with game info
#' @param con DBI connection
#' @return tibble of moves joined with game info
load_moves_with_games <- function(con) {
  query <- "
    SELECT
      m.*,
      g.platform,
      g.white_rating,
      g.black_rating,
      g.time_control,
      g.time_control_seconds,
      g.increment_seconds,
      g.date_played,
      g.result,
      g.eco_code,
      g.opening_name,
      pw.username as white_username,
      pb.username as black_username
    FROM moves m
    JOIN games g ON m.game_id = g.game_id
    JOIN players pw ON g.white_player_id = pw.player_id
    JOIN players pb ON g.black_player_id = pb.player_id
    WHERE g.analysis_status = 'complete'
    ORDER BY g.date_played DESC, m.ply_number
  "
  dbGetQuery(con, query) %>%
    as_tibble() %>%
    mutate(
      color = factor(color, levels = c("white", "black")),
      game_phase = factor(game_phase, levels = c("opening", "middlegame", "endgame")),
      date_played = ymd_hms(date_played)
    )
}

#' Load moves for a specific player
#' @param con DBI connection
#' @param username Player username
#' @param platform Platform (chesscom or lichess)
#' @return tibble of player's moves
load_player_moves <- function(con, username, platform = "chesscom") {
  query <- "
    SELECT
      m.*,
      g.platform,
      g.white_rating,
      g.black_rating,
      g.time_control,
      g.time_control_seconds,
      g.date_played,
      g.result,
      g.eco_code,
      g.opening_name,
      pw.username as white_username,
      pb.username as black_username,
      CASE
        WHEN LOWER(pw.username) = LOWER(?) THEN 'white'
        ELSE 'black'
      END as player_color,
      CASE
        WHEN LOWER(pw.username) = LOWER(?) THEN g.white_rating
        ELSE g.black_rating
      END as player_rating
    FROM moves m
    JOIN games g ON m.game_id = g.game_id
    JOIN players pw ON g.white_player_id = pw.player_id
    JOIN players pb ON g.black_player_id = pb.player_id
    WHERE g.analysis_status = 'complete'
      AND g.platform = ?
      AND (LOWER(pw.username) = LOWER(?) OR LOWER(pb.username) = LOWER(?))
    ORDER BY g.date_played DESC, m.ply_number
  "
  dbGetQuery(con, query, params = list(username, username, platform, username, username)) %>%
    as_tibble() %>%
    mutate(
      color = factor(color, levels = c("white", "black")),
      game_phase = factor(game_phase, levels = c("opening", "middlegame", "endgame")),
      player_color = factor(player_color, levels = c("white", "black")),
      date_played = ymd_hms(date_played),
      is_player_move = (color == player_color)
    )
}

#' Get database statistics
#' @param con DBI connection
#' @return list of statistics
get_db_stats <- function(con) {
  list(
    total_games = dbGetQuery(con, "SELECT COUNT(*) as n FROM games")$n,
    analyzed_games = dbGetQuery(con, "SELECT COUNT(*) as n FROM games WHERE analysis_status = 'complete'")$n,
    total_moves = dbGetQuery(con, "SELECT COUNT(*) as n FROM moves")$n,
    total_players = dbGetQuery(con, "SELECT COUNT(*) as n FROM players")$n,
    platforms = dbGetQuery(con, "SELECT platform, COUNT(*) as n FROM games GROUP BY platform") %>% as_tibble()
  )
}

# Example usage:
# con <- connect_db()
# games <- load_games(con)
# moves <- load_moves_with_games(con)
# player_moves <- load_player_moves(con, "your_username")
# disconnect_db(con)
