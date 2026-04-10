# Claude Code Handoff — Chess Insights

> Last updated: 2026-04-10
> Repo: https://github.com/Kaczor594/chess-insights.git
> Branch: master

## Project Summary

Chess Insights is an automated chess analytics pipeline for **kaczor594** (Chess.com) and **simsimlamachine** (Lichess). A Python backend fetches games via the Chess.com and Lichess APIs, analyzes every move with Stockfish, and stores results in SQLite. An R layer computes statistics (centipawn loss, move classification, opening performance) and generates interactive visualizations. A Quarto static site deployed on GitHub Pages displays the results, auto-updating daily via a `launchd`-scheduled sync script. Lichess games (simsimlamachine) are imported manually.

## Current State

- **Working:** Full pipeline — fetch → Stockfish analysis → SQLite → R analytics → Quarto site → GitHub Pages. The site is live at `https://kaczor594.github.io/chess-insights/`.
- **Working:** Daily automation via `launchd` runs `scripts/daily_sync.sh` which fetches new games (kaczor594/Chess.com only), analyzes up to 50, renders the Quarto site, and pushes `docs/` to GitHub.
- **Working:** 6-page site: Overview, Centipawn Loss trends, Openings, Game Phases, Time Management, About.
- **Working:** `best_move_san` column on `moves` table — stores engine best move in SAN notation (e.g., `Bxf6`, `O-O`). Populated automatically for new games via Stockfish analysis pipeline. Backfilled for all historical data (99.9% coverage, 417 NULLs from non-standard-position Lichess games).
- **In progress:** The accuracy metric was recently swapped from an exponential formula to plain ACPL (average centipawn loss). The user plans to design a better accuracy metric in the future.
- **Known visual fixes applied:** Dark mode theme overrides for ggplot2 and plotly, DT table readability CSS, density plot replacing violin chart.

## Environment Setup

**Python:**
```bash
cd /Users/isaackaczor/claude-projects/chess-insights
source venv/bin/activate
pip install -e python/  # installs chess-insights CLI
```

Requires Stockfish installed and configured in `config.yaml`.

**R:**
Packages auto-install on first source. Key packages: `tidyverse`, `DBI`, `RSQLite`, `plotly`, `viridis`, `scales`, `lubridate`, `glue`, `slider`, `here`, `DT`, `htmlwidgets`.

**Quarto:**
Installed via tarball at `~/.local/bin/quarto` (v1.6.42). The `brew install quarto` route requires `sudo` for the macOS .pkg installer. Ensure `~/.local/bin` is on PATH.

```bash
quarto render              # builds site to docs/
quarto preview             # local dev server
```

**GitHub Pages:** Configured to deploy from `master` branch, `/docs` folder.

## File Structure

```
_quarto.yml              # Quarto site config (darkly theme, navbar, output to docs/)
styles.css               # Chess-themed dark mode CSS
index.qmd                # Dashboard overview page
accuracy.qmd             # Centipawn loss trends page
openings.qmd             # Opening performance (DT tables + plotly)
phases.qmd               # Game phase analysis
time-management.qmd      # Time pressure & clock analysis
about.qmd                # Methodology, ACPL formula, benchmarks
R/
  functions.R            # Site wrapper: sources pipeline, overrides for dark mode + ACPL
  scripts/
    00_setup.R           # Package loading, theme_chess(), config
    01_data_loading.R    # DB connection, load_games/moves/player_moves
    02_accuracy_analysis.R  # calculate_accuracy (original formula), classify_move, etc.
    06_visualizations.R  # ggplot2/plotly plot functions
python/chess_insights/   # Python CLI: fetch, analyze commands
  api/                   # Chess.com + Lichess API clients
  analysis/              # Stockfish wrapper, game phase classification
  database/              # SQLite schema + operations
scripts/daily_sync.sh    # Automated daily: fetch → analyze → quarto render → git push
scripts/backfill_best_move_san.py  # One-time backfill: converts best_move UCI → SAN via board replay
data/chess_insights.db   # SQLite database (~64MB, gitignored)
docs/                    # Rendered site output (committed, serves GitHub Pages)
config.yaml              # Stockfish path, API delay settings
```

## Architecture

**Data flow:** Chess.com API → Python fetch → SQLite (`players`, `games`, `moves` tables) → Python Stockfish analysis → R sourcing chain (`00_setup.R` → `01_data_loading.R` → `02_accuracy_analysis.R` → `06_visualizations.R`) → `R/functions.R` (site overrides) → Quarto `.qmd` pages → `docs/` HTML.

**R sourcing chain is linear:** Each script sources the previous one. `R/functions.R` sources `06_visualizations.R` (which loads the full chain) then overrides `theme_chess()` for dark mode, `calculate_accuracy()` to return raw ACPL instead of the exponential formula, and `calculate_opening_performance()` to sort ascending.

**Database:** SQLite with 4 tables (`players`, `games`, `moves`, `sync_metadata`), 8 indexes, foreign key triggers. Access via `DBI`/`RSQLite` in R, `DatabaseManager` class in Python. The `moves` table includes `best_move` (UCI) and `best_move_san` (SAN) columns — Stockfish computes both during analysis and the pipeline stores them directly.

## Recent Changes

### Session 2026-04-10
- Added `best_move_san` TEXT column to `moves` table (schema, operations, analyze pipeline)
- Stockfish already computed `best_move_san` in `PositionAnalysis` but `analyze.py` was discarding it — now wired through to the DB
- Backfilled 365,818 / 366,235 existing moves (99.9%) via `scripts/backfill_best_move_san.py` (board replay with python-chess, no Stockfish needed)
- 417 NULLs remain from Lichess "From Position" variant games (non-standard starting positions break board replay)
- 126 rows flagged with `?` prefix (best_move was illegal in reconstructed position)
- Fetched 47 new Lichess games for simsimlamachine (last synced Jan 2026, games through Mar 8 2026)
- Analyzed all 47 new games — `best_move_san` populated automatically via updated pipeline

### Previous sessions
- `5f3f2b1` — Replaced violin chart with density plot for ACPL by time control
- `19e85c9` — Replaced accuracy formula with average centipawn loss (ACPL) metric across all pages
- `a08723a` — Fixed DT table readability for dark theme (light text, styled pagination)
- `561713c` — Fixed dark mode: light scatter points, transparent backgrounds, dark-friendly ggplot theme
- `5385a5c` — Initial commit: full Quarto site with 6 pages, automation in daily_sync.sh
- Daily auto-commits since Feb 24 updating `docs/` via the sync script

## Known Issues

- **Quarto install:** `brew install quarto` needs `sudo` on macOS. Workaround: install via tarball to `~/.local/bin/`.
- **ACPL metric is simplistic:** Raw average centipawn loss doesn't weight moves by importance or game context. The user plans to design a better metric.
- **Opening data quality:** Some openings show as "Undefined" (ECO code A00) — these are non-standard openings that Chess.com doesn't classify.
- **Critical moments table:** Checkmate moves show cp_loss of 19998 (Stockfish sentinel value for mating moves being flagged as blunders). Could be filtered out.
- **`calculate_accuracy()` override:** The site overrides this function in `R/functions.R` to return ACPL, but the original exponential formula still exists in `02_accuracy_analysis.R`. The underlying scripts are unchanged.
- **Lichess "From Position" games:** ~417 moves from variant games (e.g., game 1576) have NULL `best_move_san` because board replay from standard starting position fails. These are non-standard starting positions that can't be replayed with `chess.Board()`.
- **Lichess sync is manual:** simsimlamachine games are not part of the nightly `daily_sync.sh` automation — must run `chess-insights fetch simsimlamachine --platform lichess` manually.

## Next Steps

- [ ] Design a better accuracy metric to replace ACPL (user's stated intention)
- [ ] Filter out mating moves (cp_loss 19998) from critical moments table
- [ ] Consider filtering "Undefined" openings from the openings page
- [ ] Add `~/.local/bin` to shell PATH permanently for quarto access
- [ ] Optionally add Lichess support to the site (pipeline already supports it)
- [ ] Add simsimlamachine Lichess fetch to `daily_sync.sh` (currently manual)
- [ ] Use `best_move_san` in downstream analysis (e.g., capture analysis: comparing player's SAN vs engine's SAN for capture `x` presence)
