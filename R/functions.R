# Chess Insights - Quarto Site Functions
# Thin wrapper that sources the existing pipeline and adds site helpers

# Source the full chain (loads all packages + all functions)
source(here::here("R", "scripts", "06_visualizations.R"))

# Site constants
SITE_USERNAME <- "kaczor594"
SITE_PLATFORM <- "chesscom"

# Override theme_chess() for dark-mode site
theme_chess <- function() {
  theme_minimal() +
    theme(
      plot.title = element_text(face = "bold", size = 14, color = "#f0d9b5"),
      plot.subtitle = element_text(size = 10, color = "#adb5bd"),
      axis.title = element_text(size = 10, color = "#adb5bd"),
      axis.text = element_text(color = "#adb5bd"),
      legend.position = "bottom",
      legend.text = element_text(color = "#adb5bd"),
      legend.title = element_text(color = "#adb5bd"),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(color = "rgba(255,255,255,0.15)"),
      panel.background = element_rect(fill = "transparent", color = NA),
      plot.background = element_rect(fill = "transparent", color = NA),
      legend.background = element_rect(fill = "transparent", color = NA)
    )
}
theme_set(theme_chess())

#' Apply standard dark-mode layout to a plotly object
#' @param p plotly object
#' @return plotly object with dark layout
dark_plotly <- function(p) {
  p %>% layout(
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor = "rgba(0,0,0,0)",
    font = list(color = "#adb5bd"),
    xaxis = list(gridcolor = "rgba(255,255,255,0.15)"),
    yaxis = list(gridcolor = "rgba(255,255,255,0.15)")
  )
}

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
