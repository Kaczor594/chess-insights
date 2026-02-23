# Chess Insights - Accuracy Analysis
# Functions for calculating and analyzing move accuracy

source(here::here("R", "scripts", "01_data_loading.R"))

#' Calculate accuracy from centipawn loss
#' Uses Chess.com's accuracy formula approximation
#' @param centipawn_loss Centipawn loss value
#' @return Accuracy percentage (0-100)
calculate_accuracy <- function(centipawn_loss) {
  # Handle NA and negative values
  cp_loss <- pmax(0, centipawn_loss, na.rm = TRUE)
  cp_loss <- ifelse(is.na(cp_loss), 0, cp_loss)

  # Chess.com-style accuracy formula
  # Accuracy drops exponentially with centipawn loss
  accuracy <- 103.1668 * exp(-0.04354 * cp_loss) - 3.1668
  accuracy <- pmax(0, pmin(100, accuracy))

  return(accuracy)
}

#' Classify move quality based on centipawn loss
#' @param centipawn_loss Centipawn loss value
#' @return Factor with move classification
classify_move <- function(centipawn_loss) {
  case_when(
    is.na(centipawn_loss) ~ "Unknown",
    centipawn_loss <= 0 ~ "Best",
    centipawn_loss <= 10 ~ "Excellent",
    centipawn_loss <= 25 ~ "Good",
    centipawn_loss <= 50 ~ "Inaccuracy",
    centipawn_loss <= 100 ~ "Mistake",
    centipawn_loss <= 300 ~ "Blunder",
    TRUE ~ "Blunder"
  ) %>%
    factor(levels = c("Best", "Excellent", "Good", "Inaccuracy", "Mistake", "Blunder", "Unknown"))
}

#' Calculate game accuracy for each player
#' @param moves tibble of moves with centipawn_loss
#' @return tibble with game_id, white_accuracy, black_accuracy
calculate_game_accuracy <- function(moves) {
  moves %>%
    filter(!is.na(centipawn_loss)) %>%
    group_by(game_id, color) %>%
    summarise(
      avg_cp_loss = mean(centipawn_loss, na.rm = TRUE),
      accuracy = calculate_accuracy(avg_cp_loss),
      n_moves = n(),
      .groups = "drop"
    ) %>%
    pivot_wider(
      names_from = color,
      values_from = c(avg_cp_loss, accuracy, n_moves),
      names_glue = "{color}_{.value}"
    )
}

#' Calculate accuracy by game phase
#' @param moves tibble of moves
#' @return tibble with accuracy by phase
calculate_phase_accuracy <- function(moves) {
  moves %>%
    filter(!is.na(centipawn_loss), !is.na(game_phase)) %>%
    group_by(game_id, color, game_phase) %>%
    summarise(
      avg_cp_loss = mean(centipawn_loss, na.rm = TRUE),
      accuracy = calculate_accuracy(avg_cp_loss),
      n_moves = n(),
      .groups = "drop"
    )
}

#' Calculate accuracy trend over time
#' @param player_moves tibble of player moves
#' @param window_size Number of games for rolling average
#' @return tibble with accuracy trend
calculate_accuracy_trend <- function(player_moves, window_size = 10) {
  player_moves %>%
    filter(is_player_move, !is.na(centipawn_loss)) %>%
    group_by(game_id, date_played, player_rating) %>%
    summarise(
      avg_cp_loss = mean(centipawn_loss, na.rm = TRUE),
      accuracy = calculate_accuracy(avg_cp_loss),
      n_moves = n(),
      .groups = "drop"
    ) %>%
    arrange(date_played) %>%
    mutate(
      game_num = row_number(),
      rolling_accuracy = slider::slide_dbl(
        accuracy,
        mean,
        .before = window_size - 1,
        .complete = FALSE
      )
    )
}

#' Calculate time-based accuracy (moves under time pressure)
#' @param moves tibble of moves with clock data
#' @return tibble with accuracy by time remaining
calculate_time_accuracy <- function(moves) {
  moves %>%
    filter(!is.na(centipawn_loss), !is.na(clock_time_remaining)) %>%
    mutate(
      time_category = case_when(
        clock_time_remaining <= 10 ~ "Critical (<10s)",
        clock_time_remaining <= 30 ~ "Low (10-30s)",
        clock_time_remaining <= 60 ~ "Medium (30-60s)",
        clock_time_remaining <= 180 ~ "Comfortable (1-3m)",
        TRUE ~ "Plenty (>3m)"
      ) %>%
        factor(levels = c("Critical (<10s)", "Low (10-30s)", "Medium (30-60s)",
                          "Comfortable (1-3m)", "Plenty (>3m)"))
    ) %>%
    group_by(time_category) %>%
    summarise(
      avg_cp_loss = mean(centipawn_loss, na.rm = TRUE),
      accuracy = calculate_accuracy(avg_cp_loss),
      n_moves = n(),
      .groups = "drop"
    )
}

#' Calculate move quality distribution
#' @param moves tibble of moves
#' @return tibble with move quality counts
calculate_move_distribution <- function(moves) {
  moves %>%
    filter(!is.na(centipawn_loss)) %>%
    mutate(move_quality = classify_move(centipawn_loss)) %>%
    count(move_quality) %>%
    mutate(
      pct = n / sum(n) * 100
    )
}

#' Identify critical moments (blunders and mistakes)
#' @param moves tibble of moves
#' @param min_cp_loss Minimum centipawn loss to flag
#' @return tibble of critical moves
identify_critical_moments <- function(moves, min_cp_loss = 100) {
  moves %>%
    filter(centipawn_loss >= min_cp_loss) %>%
    select(
      game_id, ply_number, color, san, centipawn_loss,
      eval_before, eval_after, best_move, game_phase
    ) %>%
    arrange(desc(centipawn_loss))
}

#' Calculate opening performance
#' @param moves tibble of moves with opening info
#' @return tibble with accuracy by opening
calculate_opening_performance <- function(moves) {
  moves %>%
    filter(!is.na(centipawn_loss), !is.na(eco_code)) %>%
    group_by(eco_code, opening_name) %>%
    summarise(
      avg_cp_loss = mean(centipawn_loss, na.rm = TRUE),
      accuracy = calculate_accuracy(avg_cp_loss),
      n_games = n_distinct(game_id),
      n_moves = n(),
      .groups = "drop"
    ) %>%
    filter(n_games >= 3) %>%  # Minimum games for statistical relevance
    arrange(desc(accuracy))
}
