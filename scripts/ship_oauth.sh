#!/usr/bin/env bash
# Robinhood MCP auth ONLY — verifies local auth (runs the interactive /mcp flow
# only if needed), then ships the minimal auth bundle to the Railway volume in
# argv-safe chunks. Rerunnable; completed steps skip themselves.
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

echo "== shipping auth to the volume (chunked, argv-safe) =="
# railway ssh needs a local SSH key; generate a passphrase-less one if absent.
if [ ! -f "$HOME/.ssh/id_ed25519" ] && [ ! -f "$HOME/.ssh/id_rsa" ]; then
  echo "no SSH key found — generating one (~/.ssh/id_ed25519)"
  ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -q || die "ssh-keygen"
fi
WORK="$(mktemp -d)"
# Only the auth-critical files — not logs/caches/projects (that's what blew ARG_MAX).
tar -C "$CLAUDE_CONFIG_DIR" -czf "$WORK/cfg.tgz" \
  $(cd "$CLAUDE_CONFIG_DIR" && ls -d .credentials.json .claude.json settings.json 2>/dev/null || true)
[ -s "$WORK/cfg.tgz" ] || tar -C "$CLAUDE_CONFIG_DIR" --exclude='./projects' \
  --exclude='./shell-snapshots' --exclude='./todos' --exclude='./statsig' \
  --exclude='./logs' --exclude='./cache' -czf "$WORK/cfg.tgz" .
base64 < "$WORK/cfg.tgz" | tr -d '\n' > "$WORK/cfg.b64"
split -b 40000 "$WORK/cfg.b64" "$WORK/chunk_"

railway ssh -- bash -c "rm -f /tmp/rhcfg.b64" || die "railway ssh unreachable"
for c in "$WORK"/chunk_*; do
  railway ssh -- bash -c "printf '%s' '$(cat "$c")' >> /tmp/rhcfg.b64" \
    || die "chunk transfer ($c) — rerun the script, it restarts the transfer cleanly"
done
railway ssh -- bash -c "mkdir -p /data/claude && base64 -d < /tmp/rhcfg.b64 > /tmp/rhcfg.tgz && tar -xzf /tmp/rhcfg.tgz -C /data/claude && rm -f /tmp/rhcfg.b64 /tmp/rhcfg.tgz && echo UNPACKED_OK" \
  || die "remote unpack"
rm -rf "$WORK"

echo "== verifying FROM the container (the one that matters) =="
railway ssh -- bash -c "cd /app && export CLAUDE_CONFIG_DIR=/data/claude && claude -p '$Q' --allowedTools 'mcp__robinhood__*'" \
  || die "container verify"

printf "\n\033[32mAUTH SHIPPED.\033[0m The engine is fully self-driving from the next premarket run.\n"
