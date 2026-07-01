# EXECUTOR INFRA — Claude Code always-on trading rails
Blake-style architecture: **autonomous eyes, human trigger finger, one-tap Telegram approval.**

```
executor-infra/
├── CLAUDE.md                  # charter — auto-loaded every Claude Code run
├── prompts/morning_pulse.md   # the daily job
├── journal.md                 # append-only audit trail (pulses + executed trades)
├── .executor.env.example      # copy to ~/.executor.env, fill in your Telegram secrets
├── scripts/
│   ├── risk_check.py          # hard caps enforced in CODE (agent can't talk past them)
│   ├── test_risk_check.py     # 12-case self-test proving the gate actually gates
│   ├── telegram.py            # propose / wait-for-YES / send
│   ├── preflight.sh           # one-shot readiness check before you arm cron
│   └── morning_pulse.sh       # cron wrapper w/ --max-turns & --max-budget-usd
└── state/
    ├── positions.json         # your live book (pre-seeded: BRK.B, XLV, GDX)
    ├── pending/               # trade proposals awaiting approval
    └── settlement.json        # unsettled-funds guard for the cash account
```

## The execution path (why this can't rug you)
LLM proposes → `risk_check.py` (deterministic code: 7% cap, sleeve caps, circuit
breakers) must print PASS → Telegram proposal sent to you → you reply `YES t004`
→ only then the order is placed via Robinhood MCP → journaled.
Any FAIL / NO / 30-min silence = no trade. Two independent gates, one of them is you.

## Setup (~20 min)
1. **Claude Code** on the box that will run this (Mac or a $5 VPS):
   `npm install -g @anthropic-ai/claude-code` → `claude` → log in.
   Docs: https://code.claude.com/docs/en/headless
2. **Robinhood MCP** (agentic account must be authorized on that machine):
   `claude mcp add --transport http robinhood https://agent.robinhood.com/mcp/trading`
   then run `claude`, `/mcp`, complete OAuth. Verify with a quote pull.
   (If the URL differs, check Robinhood's agentic-trading docs — connector auth is per-machine.)
3. **Telegram bot:** message @BotFather → /newbot → token. Message your bot once,
   get chat id from `https://api.telegram.org/bot<TOKEN>/getUpdates`. Then:
   `echo 'export TELEGRAM_BOT_TOKEN=...' >> ~/.executor.env`
   `echo 'export TELEGRAM_CHAT_ID=...'  >> ~/.executor.env`
   Test: `source ~/.executor.env && python3 scripts/telegram.py send "Executor online"`
4. **Cron:** `chmod +x scripts/morning_pulse.sh` then `crontab -e`:
   `15 9 * * 1-5 cd /path/to/executor-infra && ./scripts/morning_pulse.sh >> state/pulse.log 2>&1`

## Where to run it (Blake's "computer must be open" problem)
- **Your Mac + cron** — free, but sleeps when the lid closes. Fine to start.
- **$5/mo VPS** —真 always-on. Recommended once this proves useful.
- **Claude Code Routines (cloud)** — runs on Anthropic infra even with your machine off
  (plan-limited runs/day), but MCP auth + secrets are simpler to reason about on your own box.

## Verify the build (no account or secrets needed)
The load-bearing safety component is `risk_check.py` — if it can be talked around, nothing
else matters. It ships with a self-test that runs the gate as a subprocess against fixture
books and asserts each verdict:
```
python3 scripts/test_risk_check.py     # 12/12 cases: caps bite, exits stay open
```
Once your Telegram secrets are in `~/.executor.env`, run the full readiness check before
arming cron (validates env + state files, runs the gate self-test, sends one test message):
```
./scripts/preflight.sh                 # PREFLIGHT PASS = safe to arm cron
```

## Ops notes
- Approvals only accepted from YOUR chat id — replies from anyone else are ignored.
- `--max-budget-usd 1.50` and `--max-turns 30` cap each run; a runaway loop dies cheap.
- flock prevents overlapping pulse runs.
- Keep using the Claude.ai project for deep underwriting/weekly reviews; this repo is
  the monitoring + alerting + approval loop. Same charter, two surfaces.
- Not financial advice; expected outcome of a max-aggression micro account is loss of
  principal. The rails exist to make ruin structurally hard, not to promise returns.
