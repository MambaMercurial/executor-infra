# executor-infra

An agentic investing repo for Claude Code. **The LLM proposes; deterministic code and a human decide.** Charter v3.0 — sicko mode: daily hunting, midday scans, a permanently loaded pipeline — with every hard rail exactly where it was.

```
executor-infra/
├── CLAUDE.md                   # THE CHARTER (v3.0) — auto-loaded every Claude Code run
├── journal.md                  # trade log + learning loop
├── Dockerfile                  # Railway cron image
├── railway.json                # Railway config-as-code (cron schedule)
├── .executor.env.example       # copy to ~/.executor.env for local/VPS runs
├── docs/
│   ├── 00_MASTER_2026-08-04.md # archival source-of-truth compilation (as imported)
│   ├── 01_PRINCIPLES.md        # operating constitution + survival math
│   ├── 02_DRL_OVERLAY.md       # the Milione amendment
│   └── 03_OPS_NOTES.md         # Robinhood MCP quirks, account state, cadence
├── prompts/
│   ├── morning_pulse.md        # the daily headless job
│   ├── midday_scan.md          # the daily hunt run — keeps the pipeline loaded
│   └── weekly_review.md        # the substantive weekly session
├── scripts/
│   ├── risk_check.py           # hard caps enforced in CODE, not prompts
│   ├── test_risk_check.py      # self-test proving the gate actually gates
│   ├── telegram.py             # propose / wait-for-YES / send
│   ├── preflight.sh            # one-shot readiness check before you arm cron
│   ├── morning_pulse.sh        # pulse runner (takes a prompt file; cron/Railway both use it)
│   └── railway_pulse.sh        # Railway container entrypoint
└── state/
    ├── positions.json          # the live book (verified flat: $198.74 cash)
    ├── settlement.json         # unsettled-funds guard for the cash account
    └── pending/                # proposals awaiting approval
```

## The execution path (why this can't rug you)

```
LLM proposes
  → risk_check.py  (deterministic: 7% cap, sleeve caps, circuit breakers, recomputed
                    max loss, settlement guard) must print PASS
  → Telegram proposal sent to you
  → you reply `YES t004`
  → only then is the order placed via the Robinhood MCP
  → journaled
```

Any FAIL, any NO, or 30 minutes of silence = no trade. **Two independent gates, one of which is you.** The validator recomputes max loss itself rather than trusting the agent's arithmetic — the caps live in code so they cannot be talked around.

Where the aggression lives instead: tempo. Two scheduled runs per trading day (pulse + hunt), 2–5 pre-underwritten candidates always sitting in `state/pending/`, and same-run SELL proposals the moment a thesis breaks. High-frequency *underwriting*, not high-frequency orders — a cash account with T+1 settlement and a human gate physically cannot be an HFT shop, and the system doesn't pretend otherwise.

## Verify the build (no account or secrets needed)

```
python3 scripts/test_risk_check.py     # the gate self-test: caps bite, exits stay open
```

Once Telegram secrets exist, run `./scripts/preflight.sh` before arming any schedule.

## Deploy on Railway (the chosen always-on host)

1. Move this to its own repo (see below), connect it to a new Railway project.
2. `railway.json` builds the Dockerfile and sets the cron: **13:15 UTC weekdays = 9:15am ET** morning pulse. Add a **second service** on the same repo for the midday hunt with `PULSE_PROMPT=prompts/midday_scan.md` and cron `30 16 * * 1-5` (12:30pm ET).
   *(Cron times are UTC and assume EDT; shift to `15 14` / `30 17` when EST returns in November.)*
3. Service variables: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. **Mount a volume at `/data`.** Claude Code config (`CLAUDE_CONFIG_DIR=/data/claude`) lives there so MCP auth survives redeploys.
5. **One-time Robinhood OAuth:** MCP auth is per-machine and interactive. `railway ssh` into the service, run `claude` → `/mcp` → complete the Robinhood OAuth, confirm with a quote pull, exit. The token persists on the volume.
   *If the ssh/OAuth dance proves brittle, a $5 VPS with plain cron is the honest fallback — same scripts, zero container ceremony.*
6. Until OAuth is done, runs fail loudly to Telegram instead of trading. Nothing silent.

### Local / VPS alternative

```bash
npm install -g @anthropic-ai/claude-code && claude   # log in
claude mcp add --transport http robinhood https://agent.robinhood.com/mcp/trading
# then: claude → /mcp → OAuth, verify with a quote pull
cp .executor.env.example ~/.executor.env             # fill in Telegram secrets
./scripts/preflight.sh
crontab -e
#  15 9  * * 1-5  cd /path/to/executor-infra && ./scripts/morning_pulse.sh >> state/pulse.log 2>&1
#  30 12 * * 1-5  cd /path/to/executor-infra && ./scripts/morning_pulse.sh prompts/midday_scan.md >> state/pulse.log 2>&1
```

## Moving this to its own repo

This directory is fully self-contained — nothing in it references the parent repo. Once an empty `executor-infra` repo exists on GitHub (and the Claude GitHub app has access, so the agent can push):

```bash
git subtree split --prefix=executor-infra -b executor-standalone
git push git@github.com:MambaMercurial/executor-infra.git executor-standalone:main
```

## Open items

- [ ] **Complete the Robinhood investor-profile questionnaire** — this currently blocks trade #2 on the agentic account.
- [ ] Create the standalone `executor-infra` GitHub repo + grant the Claude GitHub app access, then run the subtree split above.
- [ ] Stand up the Railway project (two cron services + volume + one-time OAuth).
- [ ] First funded pipeline: run the midday scan manually once and load 2–3 candidates.

## Division of labor

- **This repo is the eyes** — daily pulses, alerts, one-tap approvals, journaling.
- **The Claude.ai project is the brain** — deep underwriting, weekly review, edge tracking, charter amendments.
- Same charter, two surfaces. When the charter changes in one place, change it in both.

---

*Not financial advice. The honest expected outcome of a max-aggression micro-account is loss of principal. The rails exist to make ruin structurally hard, not to promise returns.*
