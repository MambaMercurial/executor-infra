#!/usr/bin/env bash
# railway_pulse.sh — container entrypoint for Railway cron runs.
# Env required (set in Railway service variables):
#   ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# Optional:
#   PULSE_PROMPT  — prompt file for this service (default prompts/morning_pulse.md).
#                   Run the midday scan as a second Railway service pointing at the
#                   same repo with PULSE_PROMPT=prompts/midday_scan.md and its own
#                   cronSchedule.
# Volume: mount at /data so Robinhood MCP OAuth (CLAUDE_CONFIG_DIR) persists.
set -euo pipefail
cd "$(dirname "$0")/.."

export CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-/data/claude}"
mkdir -p "$CLAUDE_CONFIG_DIR"

# Register the Robinhood MCP once; OAuth itself is completed interactively one time
# via `railway ssh` (see README). Until then, runs alert instead of trading.
claude mcp list 2>/dev/null | grep -qi robinhood \
  || claude mcp add --transport http robinhood https://agent.robinhood.com/mcp/trading \
  || true

exec ./scripts/morning_pulse.sh "${PULSE_PROMPT:-prompts/morning_pulse.md}"
