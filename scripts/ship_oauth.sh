#!/usr/bin/env bash
# Robinhood MCP auth — PLAN C: ships the auth bundle to the container via a
# Railway service VARIABLE (the channel that already works for the Telegram
# tokens). No ssh, no keys, no chunks. Rerunnable; completed steps skip.
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

Q="Use the robinhood MCP to pull a live quote for SPY. Print ONLY the last price."

echo "== checking local auth =="
if claude -p "$Q" --allowedTools "mcp__robinhood__*" 2>/dev/null | grep -qE '[0-9]'; then
  echo "already authenticated — skipping the /mcp step"
else
  cat <<'MSG'
A Claude session opens next. Do exactly:
  1. /mcp
  2. robinhood -> Authenticate -> approve in the browser
  3. Ctrl+C twice to quit
MSG
  read -rp "Press Enter to start..." _
  claude || true
  echo "== verifying locally =="
  claude -p "$Q" --allowedTools "mcp__robinhood__*" | grep -E '[0-9]' || die "local verify — redo /mcp auth"
fi

echo "== packing minimal auth bundle =="
WORK="$(mktemp -d)"
tar -C "$CLAUDE_CONFIG_DIR" -czf "$WORK/cfg.tgz" \
  $(cd "$CLAUDE_CONFIG_DIR" && ls -d .credentials.json .claude.json settings.json 2>/dev/null || true)
[ -s "$WORK/cfg.tgz" ] || tar -C "$CLAUDE_CONFIG_DIR" --exclude='./projects' \
  --exclude='./shell-snapshots' --exclude='./todos' --exclude='./statsig' \
  --exclude='./logs' --exclude='./cache' -czf "$WORK/cfg.tgz" .
B64="$(base64 < "$WORK/cfg.tgz" | tr -d '\n')"
rm -rf "$WORK"
echo "bundle size: ${#B64} chars (base64)"
[ "${#B64}" -lt 200000 ] || die "auth bundle unexpectedly large — tell the agent"

echo "== setting Railway variable (triggers redeploy) =="
railway variables --set "CLAUDE_AUTH_B64=$B64" >/dev/null || die "railway variables --set"

printf "\n\033[32mAUTH SHIPPED (via Railway variable).\033[0m\n"
cat <<'DONE'
Railway is redeploying the service now. What to watch (no further action):
  1. Telegram: "🟢 Executor engine online" (the redeploy boot)
  2. Telegram: "🔑 Robinhood auth seeded onto the volume"  <- the win
  3. Next premarket brief reads AUTHENTICATED and reconciles the real book.
DONE
