#!/usr/bin/env bash
# morning_pulse.sh — the always-on pulse runner. Same script for every scheduled run;
# pass a prompt file to select the job (defaults to the morning pulse).
#
#   ./scripts/morning_pulse.sh                          # morning pulse
#   ./scripts/morning_pulse.sh prompts/midday_scan.md   # midday hunt
#   ./scripts/morning_pulse.sh prompts/weekly_review.md # weekly review
#
# crontab example (9:15am ET weekdays; adjust TZ):
#   15 9  * * 1-5  cd /path/to/executor-infra && ./scripts/morning_pulse.sh >> state/pulse.log 2>&1
#   30 12 * * 1-5  cd /path/to/executor-infra && ./scripts/morning_pulse.sh prompts/midday_scan.md >> state/pulse.log 2>&1
#
# Secrets come from the environment (Railway) or ~/.executor.env (cron on your own box).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f ~/.executor.env ]; then source ~/.executor.env; fi

PROMPT="${1:-prompts/morning_pulse.md}"
[ -f "$PROMPT" ] || { echo "prompt file not found: $PROMPT"; exit 1; }

# Prevent overlapping runs
exec 9>state/.pulse.lock
flock -n 9 || { echo "pulse already running"; exit 0; }

claude -p "$(cat "$PROMPT")" \
  --allowedTools "Read,Write,Edit,Bash(python3 scripts/*),mcp__robinhood__*" \
  --max-turns 30 \
  --max-budget-usd 1.50 \
  --output-format json > state/last_pulse.json || {
    python3 scripts/telegram.py send "⚠️ Executor pulse failed ($PROMPT) — check logs" || true
    exit 1
  }
