#!/bin/bash
# Daily Chess.com game sync script
# Fetches new games and analyzes them

set -e

PROJECT_DIR="/Users/isaackaczor/claude-projects/chess-insights"
VENV_DIR="$PROJECT_DIR/venv"
LOG_FILE="$PROJECT_DIR/logs/sync.log"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

# Log start time
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting daily sync" >> "$LOG_FILE"

# Activate virtual environment and run fetch
source "$VENV_DIR/bin/activate"
cd "$PROJECT_DIR"

# Fetch new games from Chess.com
if chess-insights fetch kaczor594 >> "$LOG_FILE" 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Fetch completed successfully" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Fetch failed" >> "$LOG_FILE"
    exit 1
fi

# Run analysis on new games
chess-insights analyze --limit 50 >> "$LOG_FILE" 2>&1

# Render Quarto site
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Rendering Quarto site" >> "$LOG_FILE"
if quarto render >> "$LOG_FILE" 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Quarto render completed" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Quarto render failed" >> "$LOG_FILE"
fi

# Commit and push updated site
git add docs/
if ! git diff --cached --quiet; then
    git commit -m "Update site: $(date '+%Y-%m-%d %H:%M:%S')"
    git push >> "$LOG_FILE" 2>&1
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Site pushed to GitHub" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - No site changes to commit" >> "$LOG_FILE"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Daily sync completed" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
