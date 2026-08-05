#!/usr/bin/env bash
# Execution bridge: tightly-scoped headless Claude run that places ONE order.
# Called by the engine daemon after the deterministic risk gate has passed.
set -euo pipefail
cd "$(dirname "$0")/.."
OID="${1:?usage: execute_order.sh <order-id>}"

claude -p "$(cat prompts/execute_order.md)

ORDER_ID: ${OID}" \
  --allowedTools "Read,Write,mcp__robinhood__*" \
  --max-turns 12 \
  --max-budget-usd 0.40 \
  --model haiku \
  --output-format json > "state/orders/results/${OID}.bridge.json" 2>&1 || true
