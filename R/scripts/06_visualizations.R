# Chess Insights - Visualizations
# ggplot2 and plotly visualizations

source(here::here("R", "scripts", "02_accuracy_analysis.R"))

#' Plot accuracy distribution histogram
#' @param game_accuracy tibble from calculate_game_accuracy()
#' @return ggplot object
plot_accuracy_distribution <- function(game_accuracy) {
  game_accuracy %>%
    pivot_longer(
      cols = c(white_accuracy, black_accuracy),
      names_to = "color",
      values_to = "accuracy"
    ) %>%
    mutate(color = str_remove(color, "_accuracy") %>% str_to_title()) %>%
    ggplot(aes(x = accuracy, fill = color)) +
    geom_histogram(bins = 30, alpha = 0.7, position = "identity") +
    scale_fill_manual(values = c("White" = "#f0d9b5", "Black" = "#b58863")) +
    labs(
      title = "Game Accuracy Distribution",
      subtitle = "Distribution of average accuracy per game by color",
      x = "Accuracy (%)",
      y = "Number of Games",
      fill = "Color"
    ) +
    theme(legend.position = "top")
}

#' Plot accuracy by game phase
#' @param phase_accuracy tibble from calculate_phase_accuracy()
#' @return ggplot object
plot_phase_accuracy <- function(phase_accuracy) {
  phase_accuracy %>%
    group_by(game_phase) %>%
    summarise(
      mean_accuracy = mean(accuracy, na.rm = TRUE),
      sd_accuracy = sd(accuracy, na.rm = TRUE),
      n = n(),
      .groups = "drop"
    ) %>%
    ggplot(aes(x = game_phase, y = mean_accuracy, fill = game_phase)) +
    geom_col(width = 0.7) +
    geom_errorbar(
      aes(ymin = mean_accuracy - sd_accuracy, ymax = mean_accuracy + sd_accuracy),
      width = 0.2
    ) +
    scale_fill_viridis_d(option = "plasma", begin = 0.2, end = 0.8) +
    labs(
      title = "Accuracy by Game Phase",
      subtitle = "Average accuracy with standard deviation",
      x = "Game Phase",
      y = "Accuracy (%)"
    ) +
    theme(legend.position = "none") +
    coord_cartesian(ylim = c(0, 100))
}

#' Plot accuracy trend over time
#' @param accuracy_trend tibble from calculate_accuracy_trend()
#' @return ggplot object
plot_accuracy_trend <- function(accuracy_trend) {
  p <- accuracy_trend %>%
    ggplot(aes(x = game_num)) +
    geom_point(aes(y = accuracy), alpha = 0.3, size = 1) +
    geom_line(aes(y = rolling_accuracy), color = "#2E86AB", linewidth = 1) +
    labs(
      title = "Accuracy Trend Over Time",
      subtitle = "Individual game accuracy (points) with rolling average (line)",
      x = "Game Number",
      y = "Accuracy (%)"
    ) +
    coord_cartesian(ylim = c(0, 100))

  p
}

#' Plot accuracy vs time remaining (interactive)
#' @param time_accuracy tibble from calculate_time_accuracy()
#' @return plotly object
plot_time_accuracy_interactive <- function(time_accuracy) {
  p <- time_accuracy %>%
    ggplot(aes(x = time_category, y = accuracy, fill = time_category)) +
    geom_col() +
    geom_text(aes(label = sprintf("%.1f%%", accuracy)), vjust = -0.5) +
    scale_fill_viridis_d(option = "turbo", begin = 0.1, end = 0.9) +
    labs(
      title = "Accuracy by Time Remaining",
      subtitle = "How time pressure affects move quality",
      x = "Time Remaining",
      y = "Accuracy (%)"
    ) +
    theme(
      legend.position = "none",
      axis.text.x = element_text(angle = 45, hjust = 1)
    ) +
    coord_cartesian(ylim = c(0, 100))

  ggplotly(p, tooltip = c("y", "text"))
}

#' Plot move quality distribution
#' @param move_dist tibble from calculate_move_distribution()
#' @return ggplot object
plot_move_distribution <- function(move_dist) {
  move_colors <- c(
    "Best" = "#4CAF50",
    "Excellent" = "#8BC34A",
    "Good" = "#CDDC39",
    "Inaccuracy" = "#FFC107",
    "Mistake" = "#FF9800",
    "Blunder" = "#F44336",
    "Unknown" = "#9E9E9E"
  )

  move_dist %>%
    ggplot(aes(x = move_quality, y = n, fill = move_quality)) +
    geom_col() +
    geom_text(aes(label = sprintf("%.1f%%", pct)), vjust = -0.5, size = 3) +
    scale_fill_manual(values = move_colors) +
    labs(
      title = "Move Quality Distribution",
      subtitle = "Classification of moves by centipawn loss",
      x = "Move Quality",
      y = "Number of Moves"
    ) +
    theme(legend.position = "none")
}

#' Plot centipawn loss over game
#' @param game_moves tibble of moves for a single game
#' @return ggplot object
plot_game_cp_loss <- function(game_moves) {
  game_moves %>%
    ggplot(aes(x = ply_number, y = centipawn_loss, color = color)) +
    geom_line() +
    geom_point(size = 2) +
    scale_color_manual(values = c("white" = "#f0d9b5", "black" = "#b58863")) +
    geom_hline(yintercept = c(50, 100), linetype = "dashed", alpha = 0.5) +
    annotate("text", x = 1, y = 50, label = "Inaccuracy", hjust = 0, size = 3) +
    annotate("text", x = 1, y = 100, label = "Mistake", hjust = 0, size = 3) +
    labs(
      title = "Centipawn Loss Throughout Game",
      x = "Ply Number",
      y = "Centipawn Loss",
      color = "Color"
    ) +
    theme(legend.position = "top")
}

#' Plot evaluation graph for a game
#' @param game_moves tibble of moves for a single game
#' @return ggplot object
plot_game_evaluation <- function(game_moves) {
  game_moves %>%
    mutate(
      eval_display = case_when(
        is_mate_after == 1 & mate_in_n_after > 0 ~ 10,
        is_mate_after == 1 & mate_in_n_after < 0 ~ -10,
        TRUE ~ pmax(-10, pmin(10, eval_after / 100))
      )
    ) %>%
    ggplot(aes(x = ply_number, y = eval_display)) +
    geom_area(fill = "#f0d9b5", alpha = 0.3) +
    geom_line(color = "#2E86AB", linewidth = 1) +
    geom_hline(yintercept = 0, linetype = "solid", color = "gray50") +
    scale_y_continuous(
      limits = c(-10, 10),
      breaks = seq(-10, 10, 2),
      labels = function(x) ifelse(abs(x) == 10, paste0(ifelse(x > 0, "+", ""), "M"), x)
    ) +
    labs(
      title = "Game Evaluation",
      subtitle = "Positive = White advantage, Negative = Black advantage",
      x = "Ply Number",
      y = "Evaluation (pawns)"
    )
}

#' Plot rating vs accuracy scatter
#' @param accuracy_trend tibble with player_rating and accuracy
#' @return ggplot object
plot_rating_accuracy <- function(accuracy_trend) {
  accuracy_trend %>%
    filter(!is.na(player_rating)) %>%
    ggplot(aes(x = player_rating, y = accuracy)) +
    geom_point(alpha = 0.5) +
    geom_smooth(method = "lm", color = "#2E86AB") +
    labs(
      title = "Rating vs Accuracy",
      subtitle = "Correlation between player rating and game accuracy",
      x = "Player Rating",
      y = "Accuracy (%)"
    ) +
    coord_cartesian(ylim = c(0, 100))
}

#' Create dashboard summary
#' @param con Database connection
#' @param username Player username
#' @param platform Platform
#' @return List of plots
create_player_dashboard <- function(con, username, platform = "chesscom") {
  # Load data
  player_moves <- load_player_moves(con, username, platform)

  if (nrow(player_moves) == 0) {
    stop(glue("No analyzed games found for {username} on {platform}"))
  }

  # Calculate metrics
  phase_acc <- calculate_phase_accuracy(player_moves %>% filter(is_player_move))
  time_acc <- calculate_time_accuracy(player_moves %>% filter(is_player_move))
  move_dist <- calculate_move_distribution(player_moves %>% filter(is_player_move))
  acc_trend <- calculate_accuracy_trend(player_moves)

  # Create plots
  list(
    phase = plot_phase_accuracy(phase_acc),
    time = plot_time_accuracy_interactive(time_acc),
    distribution = plot_move_distribution(move_dist),
    trend = plot_accuracy_trend(acc_trend),
    rating = plot_rating_accuracy(acc_trend)
  )
}

#' Save plot to file
#' @param plot ggplot or plotly object
#' @param filename Filename (without extension)
#' @param width Width in inches
#' @param height Height in inches
save_plot <- function(plot, filename, width = 10, height = 6) {
  filepath <- file.path(config$output_dir, paste0(filename, ".png"))

  if (inherits(plot, "plotly")) {
    # For plotly, save as HTML
    htmlwidgets::saveWidget(
      plot,
      file.path(config$output_dir, paste0(filename, ".html")),
      selfcontained = TRUE
    )
  } else {
    ggsave(filepath, plot, width = width, height = height, dpi = 150)
  }

  message(glue("Saved plot to {filepath}"))
}
