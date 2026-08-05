#!/usr/bin/env bash
# railway_pulse.sh — container entrypoint for Railway cron runs.
# Env required (set in Railway service variables):
#   ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# Optional:
#   PULSE_PROMPT  — prompt file for this service (default prompts/morning_pulse.md).
#                   Run the midday scan as a second Railway service pointing at the
#                   same repo with PULSE_PROMPT=prompts/midday_scan.md and its own
#                   cronSchedule.
# Volume: mount at /data. It carries BOTH the Robinhood MCP OAuth (CLAUDE_CONFIG_DIR)
# and the mutable book (state/, journal.md) — the container filesystem is ephemeral,
# so anything a run writes outside /data is lost when the run exits.
set -euo pipefail
cd "$(dirname "$0")/.."

export CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-/data/claude}"
mkdir -p "$CLAUDE_CONFIG_DIR"

# Persist mutable state on the volume. The copies baked into the image only seed
# the very first run; after that the volume's book is the book.
if [ -d /data ]; then
  mkdir -p /data/executor
  for p in state journal.md; do
    [ -e "/data/executor/$p" ] || cp -r "$p" "/data/executor/$p"
    rm -rf "$p"
    ln -s "/data/executor/$p" "$p"
  done
fi

# Register the Robinhood MCP once; OAuth itself is completed interactively one time
# via `railway ssh` (see README). Until then, runs alert instead of trading.
claude mcp list 2>/dev/null | grep -qi robinhood \
  || claude mcp add --transport http robinhood https://agent.robinhood.com/mcp/trading \
  || true

exec ./scripts/morning_pulse.sh "${PULSE_PROMPT:-prompts/morning_pulse.md}"
