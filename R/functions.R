# Chess Insights - Quarto Site Functions
# Thin wrapper that sources the existing pipeline and adds site helpers

# Source the full chain (loads all packages + all functions)
source(here::here("R", "scripts", "06_visualizations.R"))

# Site constants
SITE_USERNAME <- "kaczor594"
SITE_PLATFORM <- "chesscom"

#' Get a database connection using the project config
#' @return DBI connection object
get_site_db <- function() {
  connect_db()
}

#' Load player moves for the site user
#' @param con DBI connection
#' @return tibble of player moves
load_site_player_moves <- function(con) {
  load_player_moves(con, SITE_USERNAME, SITE_PLATFORM)
}

#' Load games for the site user
#' @param con DBI connection
#' @return tibble of games filtered to the site user
load_site_games <- function(con) {
  games <- load_games(con)
  games %>%
    filter(
      tolower(white_username) == tolower(SITE_USERNAME) |
      tolower(black_username) == tolower(SITE_USERNAME)
    )
}

#' Classify time control into category
#' @param time_control_seconds Total time in seconds
#' @return character category
classify_time_control <- function(time_control_seconds) {
  case_when(
    is.na(time_control_seconds) ~ "Unknown",
    time_control_seconds < 180 ~ "Bullet",
    time_control_seconds < 600 ~ "Blitz",
    time_control_seconds < 1800 ~ "Rapid",
    TRUE ~ "Classical"
  )
}
