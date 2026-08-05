#!/usr/bin/env bash
# Robinhood MCP auth ONLY — the surgical version of bootstrap_railway.sh steps
# 3-6, for when variables are already set but the container is unauthenticated.
# Run on YOUR machine: bash scripts/ship_oauth.sh
set -uo pipefail
die() { printf "\033[31mFAILED: %s\033[0m\n" "$1"; exit 1; }

command -v railway >/dev/null || npm i -g @railway/cli || die "railway CLI install"
railway whoami >/dev/null 2>&1 || railway login || die "railway login"
railway status >/dev/null 2>&1 || railway link || die "railway link"

export CLAUDE_CONFIG_DIR="$HOME/.executor-claude"
mkdir -p "$CLAUDE_CONFIG_DIR"
command -v claude >/dev/null || npm i -g @anthropic-ai/claude-code || die "claude install"
claude mcp list 2>/dev/null | grep -qi robinhood \
  || claude mcp add --transport http robinhood https://agent.robinhood.com/mcp/trading

cat <<'MSG'
A Claude session opens next. Do exactly:
  1. /mcp
  2. robinhood -> Authenticate -> approve in the browser
  3. Ctrl+C twice to quit
MSG
read -rp "Press Enter to start..." _
claude || true

Q="Use the robinhood MCP to pull a live quote for SPY. Print ONLY the last price."
echo "== verifying locally =="
claude -p "$Q" --allowedTools "mcp__robinhood__*" || die "local verify — redo /mcp auth"

echo "== shipping auth to the volume =="
TARB64="$(tar -C "$CLAUDE_CONFIG_DIR" -czf - . | base64)"
railway ssh -- bash -c "mkdir -p /data/claude && echo '$TARB64' | base64 -d | tar -xzf - -C /data/claude" \
  || die "railway ssh transfer"

echo "== verifying FROM the container =="
railway ssh -- bash -c "cd /app && export CLAUDE_CONFIG_DIR=/data/claude && claude -p '$Q' --allowedTools 'mcp__robinhood__*'" \
  || die "container verify"

printf "\n\033[32mAUTH SHIPPED.\033[0m The next premarket run will reconcile against the real broker.\n"
