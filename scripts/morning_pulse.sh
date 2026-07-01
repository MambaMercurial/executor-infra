#!/usr/bin/env bash
# morning_pulse.sh — the daily always-on loop. Run via cron ~15 min before market open
# and optionally once mid-day. Guardrails: bounded turns, bounded spend, scoped tools.
#
# crontab example (9:15am ET weekdays; adjust TZ):
#   15 9 * * 1-5  cd /path/to/executor-infra && ./scripts/morning_pulse.sh >> state/pulse.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
source ~/.executor.env   # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Prevent overlapping runs
exec 9>state/.pulse.lock
flock -n 9 || { echo "pulse already running"; exit 0; }

claude -p "$(cat prompts/morning_pulse.md)" \
  --allowedTools "Read,Write,Edit,Bash(python3 scripts/*),mcp__robinhood__*" \
  --max-turns 30 \
  --max-budget-usd 1.50 \
  --output-format json > state/last_pulse.json || {
    python3 scripts/telegram.py send "⚠️ Executor pulse failed — check state/pulse.log"
    exit 1
  }
