#!/usr/bin/env bash
# Container entrypoint (Railway always-on worker) and local runner.
# Env: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
#      EXECUTOR_DRY_RUN=1 for simulated live fills (pre-OAuth testing)
# Volume at /data carries: Claude config (Robinhood MCP OAuth) + mutable book.
set -euo pipefail
cd "$(dirname "$0")/.."

export CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-/data/claude}"
mkdir -p "$CLAUDE_CONFIG_DIR"

# Persist mutable state on the volume; image copies seed the first boot only.
if [ -d /data ]; then
  mkdir -p /data/executor
  for p in state journal.md; do
    [ -e "/data/executor/$p" ] || cp -r "$p" "/data/executor/$p"
    rm -rf "$p"
    ln -s "/data/executor/$p" "$p"
  done
fi

# Register the Robinhood MCP for the bridge/slow-loop runs; OAuth is completed
# once interactively via `railway ssh` → claude → /mcp (persists on the volume).
claude mcp list 2>/dev/null | grep -qi robinhood \
  || claude mcp add --transport http robinhood https://agent.robinhood.com/mcp/trading \
  || true

exec python3 -u -m engine.daemon
