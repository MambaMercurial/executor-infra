#!/usr/bin/env bash
# Adversarial skeptic: the second gate for discretionary trades (replaces the
# human Telegram approval under charter v4.0). Separate context, hostile prompt.
set -euo pipefail
cd "$(dirname "$0")/.."
PID="${1:?usage: adversarial_check.sh <proposal-id>}"

claude -p "$(cat prompts/skeptic.md)

PROPOSAL: ${PID}" \
  --allowedTools "Read,Write,Bash(python3 *),mcp__robinhood__get_equity_quotes,mcp__robinhood__get_equity_fundamentals" \
  --max-turns 15 \
  --max-budget-usd 0.75 \
  --output-format json > "state/pending/${PID}.skeptic.log.json" 2>&1 || true

if [ -f "state/pending/${PID}.verdict.json" ]; then
  python3 -c "import json,sys; v=json.load(open('state/pending/${PID}.verdict.json')); print(v.get('verdict','REFUTE')); sys.exit(0 if v.get('verdict')=='CONCUR' else 1)"
else
  echo "REFUTE (no verdict file)"
  exit 1
fi
