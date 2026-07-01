#!/usr/bin/env bash
# preflight.sh — run this once after setup (and any time the pulse misbehaves).
# It checks the always-on rails WITHOUT placing any order or waiting for approval:
#   env secrets present, state files valid, risk gate self-test green, Telegram reachable.
# Exit 0 = ready to arm cron. Non-zero = fix what it prints first.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
ok(){   printf '  \033[32mok\033[0m   %s\n' "$1"; }
bad(){  printf '  \033[31mXX\033[0m   %s\n' "$1"; fail=1; }

echo "executor-infra preflight"

# 1. Secrets
[ -f "$HOME/.executor.env" ] && source "$HOME/.executor.env" || true
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] && ok "TELEGRAM_BOT_TOKEN set" || bad "TELEGRAM_BOT_TOKEN missing (see .executor.env.example)"
[ -n "${TELEGRAM_CHAT_ID:-}" ]  && ok "TELEGRAM_CHAT_ID set"  || bad "TELEGRAM_CHAT_ID missing"

# 2. State files parse
python3 - <<'PY' && ok "state/positions.json valid" || bad "state/positions.json invalid or missing"
import json; d=json.load(open("state/positions.json"))
assert "account_value" in d and "positions" in d
PY
python3 - <<'PY' && ok "state/settlement.json valid" || bad "state/settlement.json invalid"
import json,os
p="state/settlement.json"
if os.path.exists(p):
    assert isinstance(json.load(open(p)).get("unsettled_symbols",[]),list)
PY
[ -d state/pending ] && ok "state/pending/ exists" || bad "state/pending/ missing"

# 3. The deterministic gate must be green — this is the load-bearing safety component.
if python3 scripts/test_risk_check.py >/tmp/executor_selftest.out 2>&1; then
  ok "risk_check self-test ($(grep -c '\[' /tmp/executor_selftest.out) cases)"
else
  bad "risk_check self-test FAILED — see below"; sed 's/^/       /' /tmp/executor_selftest.out
fi

# 4. Telegram round-trip (only if secrets present) — sends one 'preflight ok' message.
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  if python3 scripts/telegram.py send "✅ executor-infra preflight — rails online $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1; then
    ok "Telegram send reachable (check your chat)"
  else
    bad "Telegram send failed — verify token/chat id and network"
  fi
else
  echo "  --   Telegram round-trip skipped (secrets not set)"
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "PREFLIGHT PASS — safe to arm cron (see README step 4)."
else
  echo "PREFLIGHT FAIL — resolve the XX items above before going live."
fi
exit $fail
