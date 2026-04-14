# Chess Insights — Project Instructions

## Git Workflow

- Branch: `master` (single branch)
- `docs/` is committed and serves GitHub Pages — do not gitignore it
- `data/chess_insights.db` is gitignored — never stage it
- `logs/` files grow from nightly automation — generally don't commit these
- Daily auto-commits come from `scripts/daily_sync.sh` via launchd at 3 AM

## Tooling

- **Python**: venv at `venv/`, activate with `source venv/bin/activate`
- **CLI**: `pip install -e python/` installs `chess-insights` command (fetch, analyze, status)
- **R**: Packages auto-install on first source. Entry point is `R/functions.R`.
- **Quarto**: `~/.local/bin/quarto` (v1.6.42). `quarto render` builds to `docs/`, `quarto preview` for local dev.
- **Stockfish**: Path configured in `config.yaml`

## Key Files

- `scripts/daily_sync.sh` — Nightly automation: fetch → analyze → quarto render → git push
- `python/chess_insights/database/schema.py` — SQLite schema (players, games, moves, sync_metadata)
- `python/chess_insights/database/operations.py` — DatabaseManager class for all DB operations
- `python/chess_insights/analysis/stockfish.py` — Stockfish wrapper, `PositionAnalysis` dataclass
- `python/chess_insights/commands/analyze.py` — Game analysis pipeline, writes moves to DB
- `python/chess_insights/commands/fetch.py` — Game fetching from Chess.com/Lichess APIs
- `R/functions.R` — Site-level R wrapper, sources the full R pipeline and applies overrides
- `web/app.py` — Flask puzzle trainer backend (run with `python web/app.py`, serves on port 8000)
- `web/templates/index.html` — Puzzle trainer HTML (chessboard.js + chess.js)
- `web/static/js/puzzle.js` — Client-side puzzle logic
- `web/static/css/style.css` — Dark theme styles
- `config.yaml` — Stockfish path, API delay settings
- `data/chess_insights.db` — SQLite database (~64MB, gitignored)

## Fetching Games

- Chess.com (kaczor594): `chess-insights fetch kaczor594` — runs nightly automatically
- Lichess (simsimlamachine): `chess-insights fetch simsimlamachine --platform lichess` — manual only
