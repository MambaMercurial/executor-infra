#!/usr/bin/env bash
# ONE-COMMAND SETUP — run this on YOUR machine (Mac), from anywhere:
#
#   git clone https://github.com/MambaMercurial/executor-infra && cd executor-infra
#   bash scripts/bootstrap_railway.sh
#
# It will: install/login the Railway CLI → link your service → set the service
# variables → run the Robinhood MCP OAuth locally (browser pops open, you click
# approve) → ship the resulting auth onto the Railway volume → verify a live
# quote pull FROM the container. Every step prints PASS/FAIL.
set -uo pipefail

step() { printf "\n\033[1m== %s ==\033[0m\n" "$1"; }
die()  { printf "\033[31mFAILED: %s\033[0m\n" "$1"; exit 1; }

step "1/6 Railway CLI"
command -v railway >/dev/null || npm i -g @railway/cli || die "npm install of Railway CLI"
railway whoami >/dev/null 2>&1 || railway login || die "railway login"
railway status >/dev/null 2>&1 || railway link || die "railway link (pick the executor-infra project + service)"
echo "PASS"

step "2/6 Service variables"
read -rp "  ANTHROPIC_API_KEY (create at console.anthropic.com/settings/keys): " AK
read -rp "  TELEGRAM_BOT_TOKEN: " TB
read -rp "  TELEGRAM_CHAT_ID: " TC
read -rp "  Start in DRY-RUN mode (simulated fills, week-one recommended)? [Y/n]: " DR
ARGS=(--set "ANTHROPIC_API_KEY=$AK" --set "TELEGRAM_BOT_TOKEN=$TB" --set "TELEGRAM_CHAT_ID=$TC")
[[ "${DR:-Y}" =~ ^[Yy]|^$ ]] && ARGS+=(--set "EXECUTOR_DRY_RUN=1")
railway variables "${ARGS[@]}" || die "setting variables"
echo "PASS — Railway is redeploying with the new variables"

step "3/6 Robinhood MCP OAuth (locally, in your browser)"
export CLAUDE_CONFIG_DIR="$HOME/.executor-claude"
mkdir -p "$CLAUDE_CONFIG_DIR"
command -v claude >/dev/null || npm i -g @anthropic-ai/claude-code || die "claude code install"
claude mcp list 2>/dev/null | grep -qi robinhood \
  || claude mcp add --transport http robinhood https://agent.robinhood.com/mcp/trading
cat <<'MSG'
  An interactive Claude session opens next. Do exactly this:
    1. type: /mcp
    2. select robinhood → Authenticate → approve in the browser that opens
    3. quit Claude (Ctrl+C twice)
MSG
read -rp "  Press Enter to open the session..." _
claude || true

step "4/6 Verify OAuth locally"
Q="Use the robinhood MCP to pull a live quote for SPY. Print ONLY the last price."
claude -p "$Q" --allowedTools "mcp__robinhood__*" || die "local quote pull — rerun this script and redo /mcp auth"
echo "PASS"

step "5/6 Ship auth to the Railway volume"
TARB64="$(tar -C "$CLAUDE_CONFIG_DIR" -czf - . | base64)"
railway ssh -- bash -c "mkdir -p /data/claude && echo '$TARB64' | base64 -d | tar -xzf - -C /data/claude" \
  || die "railway ssh transfer — if ssh flaked, just rerun this script; steps 1-4 are already done"
echo "PASS"

step "6/6 Verify FROM the container (the one that matters)"
railway ssh -- bash -c "cd /app && export CLAUDE_CONFIG_DIR=/data/claude && claude -p 'Use the robinhood MCP to pull a live quote for SPY. Print ONLY the last price.' --allowedTools 'mcp__robinhood__*'" \
  || die "container quote pull"
railway ssh -- bash -c "ls /data/executor/state/pending/ 2>/dev/null || echo '(pending syncs automatically on next boot)'"

printf "\n\033[32mALL DONE.\033[0m The engine is fully armed. Watch Telegram for the 🟢 online message\nand tomorrow's ~9:00 ET pre-market brief. Text STATUS to the bot anytime.\n"
