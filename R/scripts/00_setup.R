# Chess Insights - R Setup
# Package loading and configuration

# Required packages
required_packages <- c(
  "tidyverse",
  "DBI",
  "RSQLite",
  "plotly",
  "viridis",
  "scales",
  "lubridate",
  "glue"
)

# Install missing packages
install_if_missing <- function(packages) {
  new_packages <- packages[!(packages %in% installed.packages()[, "Package"])]
  if (length(new_packages) > 0) {
    message("Installing packages: ", paste(new_packages, collapse = ", "))
    install.packages(new_packages, repos = "https://cran.rstudio.com/")
  }
}

install_if_missing(required_packages)

# Load packages
suppressPackageStartupMessages({
  library(tidyverse)
  library(DBI)
  library(RSQLite)
  library(plotly)
  library(viridis)
  library(scales)
  library(lubridate)
  library(glue)
})

# Configuration
config <- list(
  db_path = here::here("data", "chess_insights.db"),
  output_dir = here::here("R", "output")
)

# Create output directory if it doesn't exist
if (!dir.exists(config$output_dir)) {
  dir.create(config$output_dir, recursive = TRUE)
}

# Theme for ggplot2
theme_chess <- function() {
  theme_minimal() +
    theme(
      plot.title = element_text(face = "bold", size = 14),
      plot.subtitle = element_text(size = 10, color = "gray40"),
      axis.title = element_text(size = 10),
      legend.position = "bottom",
      panel.grid.minor = element_blank()
    )
}

# Set default theme
theme_set(theme_chess())

message("Chess Insights R environment loaded successfully!")
message(glue("Database path: {config$db_path}"))
message(glue("Output directory: {config$output_dir}"))
