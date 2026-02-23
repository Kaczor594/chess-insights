# Chess Insights - Useful Commands

## Daily Sync

```bash
# Run sync manually (fetches new games + analyzes them)
~/claude-projects/chess-insights/scripts/daily_sync.sh

# Check sync logs
cat ~/claude-projects/chess-insights/logs/sync.log

# View recent log entries
tail -50 ~/claude-projects/chess-insights/logs/sync.log
```

## Scheduled Sync Management

```bash
# Disable automatic daily sync
launchctl unload ~/Library/LaunchAgents/com.chess-insights.daily-sync.plist

# Re-enable automatic daily sync
launchctl load ~/Library/LaunchAgents/com.chess-insights.daily-sync.plist

# Check if sync job is running
launchctl list | grep chess-insights
```

## CLI Commands

First activate the virtual environment:
```bash
source ~/claude-projects/chess-insights/venv/bin/activate
cd ~/claude-projects/chess-insights
```

Then run commands:
```bash
# Check database status
chess-insights status

# Fetch new games (incremental - only new games since last sync)
chess-insights fetch kaczor594

# Fetch ALL games (full refresh - ignores sync state)
chess-insights fetch kaczor594 --full-refresh

# Fetch from Lichess instead of Chess.com
chess-insights fetch YOUR_LICHESS_USERNAME --platform lichess

# Analyze pending games (default depth 15)
chess-insights analyze

# Analyze with higher depth (more accurate but slower)
chess-insights analyze --depth 20

# Analyze limited number of games
chess-insights analyze --limit 10
```

## MCP Server

The MCP server runs automatically when Claude Desktop starts. To test it manually:
```bash
~/claude-projects/chess-insights/venv/bin/python ~/claude-projects/chess-insights/mcp_server.py
```

## File Locations

- **Database:** `~/claude-projects/chess-insights/data/chess_insights.db`
- **Sync logs:** `~/claude-projects/chess-insights/logs/sync.log`
- **Launchd job:** `~/Library/LaunchAgents/com.chess-insights.daily-sync.plist`
- **Sync script:** `~/claude-projects/chess-insights/scripts/daily_sync.sh`
- **MCP server:** `~/claude-projects/chess-insights/mcp_server.py`
- **Claude Desktop config:** `~/Library/Application Support/Claude/claude_desktop_config.json`
