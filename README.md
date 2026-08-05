# executor-infra

**The Executor v4.0 — a baby-Medallion apparatus, honestly scoped.** Fully autonomous: deterministic Python trades and gates, LLM runs research and journal, an adversarial skeptic kills bad discretionary trades, and the operator holds a veto they never need to use. No approval taps. Paper engine measures at unlimited cadence; live dollars follow proof.

```
executor-infra/
├── CLAUDE.md                    # THE CHARTER v4.0 — the operative law
├── engine/                      # FAST LOOP — deterministic, always-on
│   ├── daemon.py                #   scheduler: polls, signals, gates, dispatch
│   ├── ledger.py                #   settlement law: settled-cash buys, GFV-impossible
│   ├── risk.py                  #   kill switches, breakers, caps — THE gate
│   ├── paper.py                 #   unbounded paper books + graduation bar
│   ├── quotes.py                #   yfinance feed (signals only; broker is truth)
│   ├── signals/meanrev.py       #   z-score dips, 200-SMA regime filter
│   ├── signals/tom.py           #   turn-of-the-month on SPY
│   ├── config.json              #   books, params, caps, calendar — versioned here
│   └── tests/test_engine.py     #   27-case self-test of every wall
├── prompts/                     # SLOW LOOP — LLM runs (daemon-invoked, capped)
│   ├── premarket.md             #   reconcile broker↔ledger, discretionary 2-gate
│   ├── postmarket.md            #   measurement, kill-criteria, journaling
│   ├── weekly_review.md         #   the learning loop
│   ├── execute_order.md         #   zero-discretion order bridge (haiku)
│   └── skeptic.md               #   adversarial 2nd gate for discretionary trades
├── scripts/
│   ├── run_daemon.sh            #   container entrypoint (volume, MCP, daemon)
│   ├── execute_order.sh         #   bridge wrapper ($0.40 cap)
│   ├── adversarial_check.sh     #   skeptic wrapper ($0.75 cap)
│   ├── risk_check.py            #   discretionary deterministic gate (+ self-test)
│   └── telegram.py              #   manual send utility
├── docs/                        # 00 master archive · 01 principles · 02 DRL
│                                # 03 ops · 04 AUTONOMY DESIGN · 05 RESEARCH NOTES
└── state/                       # ledger, engine state, paper books, pending,
                                 # orders outbox/results — lives on /data volume
```

## How an order happens (no humans involved)

**Systematic:** coded signal → `risk.py` gate (floor, breakers, caps) → `ledger.py` (settled cash / GFV law) → haiku bridge places via Robinhood MCP → Telegram notified → journaled.

**Discretionary:** LLM proposal in `state/pending/` → `risk_check.py` PASS → adversarial skeptic CONCUR (separate hostile LLM whose job is to refute) → premarket run places → notified → journaled.

**Operator veto (Telegram, anytime):** `HALT` · `RESUME` · `FLAT` · `STATUS`. Silence = system runs. That's the design.

## The honest math (see docs/04 + 05)

- Live cadence is settlement-physics-bounded: the bankroll cycles once per business day (~5 round trips/tranche/week at $200). Unlimited cadence lives in the **paper engine**, which is the measurement machine.
- No system delivers "profit every day" — the target is positive expectancy × throughput × compounding, measured net of costs, with pre-registered kill criteria.
- Books start in **paper**. Graduation to live is code-decided (≥20 clean events + evidence prior); live sizing assumes edge = 0. The LLM may de-risk autonomously, never up-risk.

## Verify the build (no secrets needed)

```bash
python3 -m engine.tests.test_engine   # 27 cases: settlement law, gates, signals
python3 scripts/test_risk_check.py    # discretionary gate self-test
```

## Deploy (Railway always-on worker)

1. Push to `main` — `railway.json` converts the service from cron to always-on
   (`cronSchedule: null`, restart ON_FAILURE, no overlap). Confirm in the dashboard
   that the service shows continuous uptime and **serverless/app-sleep is OFF**.
2. Service variables: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
   Optional first week: `EXECUTOR_DRY_RUN=1` (live path simulates fills; everything
   else real — good for validating plumbing before real orders).
3. Volume mounted at `/data` (carries MCP OAuth + the book across deploys).
4. One-time: `railway ssh` → `claude` → `/mcp` → complete Robinhood OAuth → quote
   pull to verify → exit.
5. Watch Telegram: engine-online message, then pre-market brief next trading day.

Local dev: `pip3 install -r requirements.txt && python3 -m engine.daemon` (env vars
as above; `EXECUTOR_DRY_RUN=1` recommended).

## Ops truths

- Every deploy restarts the daemon (SIGTERM-safe; state on the volume).
- The engine never trades blind: no quotes → no signals; broker is reconciled every
  pre-market; drift is journaled.
- Costs: ~$5/mo Railway + ~$4–8/trading day of capped LLM runs. At $200 the infra
  outcosts the account — this is an R&D build whose assets (telemetry, discipline,
  the machine itself) compound when capital does.

---

*Not financial advice. The honest expected outcome of a micro account remains loss of principal; the rails exist to make ruin structurally impossible while the system earns the right to scale.*
