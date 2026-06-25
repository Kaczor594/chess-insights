# Chess Insights

Automated chess analytics that turns a player's game history into an interactive
report — accuracy trends, opening performance, phase-by-phase strength, and time
management.

**Live site:** https://kaczor594.github.io/chess-insights/

## What it does

- **Ingests games** from the Chess.com and Lichess public APIs
- **Analyzes every position** with the Stockfish engine (centipawn loss per move)
- **Stores** games and move-level evaluations in a local SQLite database
- **Publishes** a multi-page [Quarto](https://quarto.org) website:
  - *Centipawn Loss* — accuracy distribution and trend over time
  - *Openings* — performance and frequency by opening
  - *Game Phases* — relative strength in the opening, middlegame, and endgame
  - *Time Management* — clock usage versus move quality

## Stack

- **R** — analysis and the Quarto report layer
- **Python** — ingestion, FEN/SAN backfill, and engine orchestration
- **Stockfish** — position evaluation
- **SQLite** — local store
- **Quarto** — static site generation (rendered to `docs/`)

## Setup

1. Install [R](https://www.r-project.org/), [Quarto](https://quarto.org), and
   [Stockfish](https://stockfishchess.org/).
2. Copy `config.yaml` and set `stockfish.path` to your local Stockfish binary.
3. Run the ingestion + analysis scripts in `scripts/` to populate the database.
4. Render the site:
   ```bash
   quarto render
   ```

## Layout

```
R/                analysis + report helper functions
python/           ingestion, engine orchestration, backfills
scripts/          sync + backfill entry points
*.qmd             report pages
config.yaml       engine + API settings
```
